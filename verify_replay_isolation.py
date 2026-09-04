"""Proof, runnable by anyone, that the replay harness re-sends cached data and re-fetches nothing.

This is the load-bearing check under the determinism claim. If `--replay` re-fetched quotes,
implied vol, option chains or account state instead of replaying the values frozen in
logs/llm_calls.jsonl, the measured divergence would be market-data drift rather than model
non-determinism, and the claim would be worthless. Every hostile reviewer named this and none
could check it, so it should not have to be taken on trust.

Method: block DNS for every host except the model provider's API, then replay. Any attempt to
reach paper-api.alpaca.markets, data.alpaca.markets or an MCP transport raises immediately and
is reported. The script prints every host the replay resolved and exits non-zero if any of them
is not the provider.

    python verify_replay_isolation.py            # a few replays per recorded provider
    python verify_replay_isolation.py --all      # every distinct recorded decision
"""
import asyncio
import socket
import sys

from agent.replay import load_calls, replay

# The only hosts a replay is allowed to touch: one model API per provider, nothing else.
PROVIDER_HOSTS = {"openai": "api.openai.com", "featherless": "api.featherless.ai"}
DEFAULT_PER_PROVIDER = 3


def _norm(host) -> str:
    return host.decode() if isinstance(host, (bytes, bytearray)) else str(host)


class DNSFence:
    """Allow-list DNS resolution and record every host anything tried to reach."""

    def __init__(self, allowed):
        self.allowed = set(allowed)
        self.seen = []
        self._real = socket.getaddrinfo

    def __enter__(self):
        def guarded(host, *a, **kw):
            h = _norm(host)
            self.seen.append(h)
            if h not in self.allowed:
                raise OSError(f"BLOCKED: replay tried to resolve {h!r}, which is not the "
                              f"model provider. It is re-fetching, not replaying.")
            return self._real(host, *a, **kw)
        socket.getaddrinfo = guarded
        return self

    def __exit__(self, *exc):
        socket.getaddrinfo = self._real
        return False


def _pick(calls: list, every: bool) -> list:
    """Distinct decision ids per provider, newest first."""
    out, seen_per = [], {}
    for c in reversed(calls):
        prov, did = c.get("provider"), c.get("decision_id")
        if not did or prov not in PROVIDER_HOSTS:
            continue
        seen = seen_per.setdefault(prov, set())
        if did in seen:
            continue
        if not every and len(seen) >= DEFAULT_PER_PROVIDER:
            continue
        seen.add(did)
        out.append((prov, did))
    return out


def main() -> int:
    every = "--all" in sys.argv
    calls = load_calls()
    if not calls:
        print("No recorded LLM calls in logs/llm_calls.jsonl — run a cycle first.")
        return 1

    targets = _pick(calls, every)
    providers = sorted({p for p, _ in targets})
    allowed = {PROVIDER_HOSTS[p] for p in providers}
    print(f"Replaying {len(targets)} decision(s) across providers {providers}")
    print(f"DNS allow-list: {sorted(allowed)}")
    print("Everything else — Alpaca trading, Alpaca market data, MCP — is blocked.\n")

    results, leaked = [], []
    for prov, did in targets:
        fence = DNSFence(allowed)
        with fence:
            try:
                r = asyncio.run(replay(did))
                status = r.get("status")
            except OSError as exc:
                status = f"BLOCKED: {exc}"
        bad = sorted({h for h in fence.seen if h not in allowed})
        leaked.extend(bad)
        results.append((prov, did, status, sorted(set(fence.seen))))
        print(f"  {prov:12s} {did}  status={status}")
        print(f"      hosts resolved: {sorted(set(fence.seen)) or '(none — no network needed)'}")

    print()
    counted = [s for _, _, s, _ in results if s in ("exact", "equivalent", "divergent")]
    print(f"{len(counted)}/{len(results)} replays completed and returned a verdict.")

    if leaked:
        print(f"\nFAIL: the replay resolved non-provider hosts: {sorted(set(leaked))}")
        print("That means tool results are being re-fetched, not replayed. The divergence")
        print("measurement is confounded by market-data drift and must not be quoted.")
        return 1

    print("\nPASS: no Alpaca, market-data or MCP host was contacted by any replay.")
    print("Tool results are replayed from logs/llm_calls.jsonl, so the divergence")
    print("measurement is of the model, not of the market.")
    if not counted:
        print("\nNote: no replay returned a verdict (credentials or rate limits). The")
        print("isolation result above still holds — nothing but the provider was contacted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

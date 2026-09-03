"""Record every LLM call in full, and re-run one from its logged inputs.

Of the 77 agentic-trading studies audited in the 2026 literature, none reached the top
reproducibility tier. Neither does this, and the honest thing is to say exactly where it
falls short rather than to imply determinism nobody has.

What this DOES give:
  * Every LLM call recorded whole -- provider, model, temperature, seed, the full message
    list, the tool schemas, and the raw response -- under a `decision_id` derived from the
    request itself, so a decision can be reconstructed from the log alone.
  * `--replay <decision_id>` re-issues that exact request and compares what comes back.

What it does NOT give, and cannot:
  * Bitwise determinism. OpenAI's `seed` is best-effort, not a guarantee. A response is only
    expected to be stable for a fixed seed while `system_fingerprint` is unchanged, and that
    fingerprint moves when the backend does, with no notice and no way to pin it. A replay
    across a fingerprint change is a different computation that happens to share inputs.
  * Anything about the market. A replay re-runs the model against the *logged* tool results,
    so it reproduces the decision, not the world the decision was made in.

So a replay reports one of three outcomes, and the middle one is the interesting one:
  exact      -- identical response text and identical tool calls
  equivalent -- same tool calls with the same arguments, different prose
  divergent  -- different action

`equivalent` is the honest target. An agent that picks the same trade for differently-worded
reasons has reproduced its decision; requiring identical prose would be a stricter test than
the thing we actually care about.

    python main.py --replay <decision_id>
    python main.py --replay list
"""
import asyncio
import hashlib
import math
import json
import os
from datetime import datetime, timezone

from agent.config import CONFIG

LOG_NAME = "llm_calls.jsonl"
# Each replay resends the full tool schemas (~21K tokens), so a back-to-back batch trips the
# key's tokens-per-minute ceiling. Spacing is cheaper than a partial report.
RETRY_SPACING_SECONDS = 12


def _path() -> str:
    return os.path.join(CONFIG.logs_dir, LOG_NAME)


def _canonical(request: dict) -> str:
    return json.dumps(request, sort_keys=True, default=str)


def decision_id(request: dict) -> str:
    """Stable id derived from the request itself, so identical inputs share an id."""
    return hashlib.sha256(_canonical(request).encode()).hexdigest()[:12]


def record_call(provider: str, model: str, request: dict, response, cost_usd: float = None,
                 role: str = None) -> str:
    """Append one LLM call to logs/llm_calls.jsonl and return its decision_id.

    Kept out of trade_log.jsonl deliberately: a full request carries the tool schemas, which
    are ~21K tokens on their own, and would bury the trade log entirely.
    """
    did = decision_id(request)
    raw, fingerprint, finish = None, None, None
    try:
        raw = response.model_dump() if hasattr(response, "model_dump") else response
        fingerprint = getattr(response, "system_fingerprint", None)
        choices = getattr(response, "choices", None)
        finish = choices[0].finish_reason if choices else None
    except Exception:
        raw = str(response)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "decision_id": did,
        "provider": provider,
        "model": model,
        "role": role,
        # Recorded even when None, because "no temperature was set" is itself the finding.
        "temperature": request.get("temperature"),
        "seed": request.get("seed"),
        # Best-effort determinism is only claimed within one fingerprint; see the docstring.
        "system_fingerprint": fingerprint,
        "finish_reason": finish,
        "cost_usd": cost_usd,
        "request": request,
        "response": raw,
    }
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    with open(_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return did


def load_calls() -> list:
    rows = []
    try:
        with open(_path(), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


def find_call(did: str):
    """Most recent recorded call with this decision_id, or None."""
    matches = [r for r in load_calls() if r.get("decision_id") == did]
    return matches[-1] if matches else None


def _extract(raw) -> tuple:
    """(text, [(tool_name, canonical_args)]) from a recorded or live OpenAI response."""
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump()
    if not isinstance(raw, dict):
        return str(raw), []
    choices = raw.get("choices") or []
    if not choices:
        return "", []
    msg = (choices[0] or {}).get("message") or {}
    text = msg.get("content") or ""
    calls = []
    for tc in (msg.get("tool_calls") or []):
        fn = (tc or {}).get("function") or {}
        args = fn.get("arguments")
        try:
            args = json.dumps(json.loads(args), sort_keys=True)
        except (TypeError, ValueError):
            args = str(args)
        calls.append((fn.get("name"), args))
    return text, calls


async def replay(did: str) -> dict:
    """Re-issue a recorded call and report whether it reproduces."""
    original = find_call(did)
    if original is None:
        return {"decision_id": did, "status": "not_found",
                "detail": f"no call with decision_id {did!r} in {_path()}"}

    if original.get("provider") != "openai":
        return {"decision_id": did, "status": "unsupported",
                "detail": f"replay is implemented for the openai path only; this call was "
                          f"{original.get('provider')!r}"}
    if not CONFIG.openai_api_key:
        return {"decision_id": did, "status": "no_credentials",
                "detail": "OPENAI_API_KEY is not set; cannot re-issue the request"}

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=CONFIG.openai_api_key)
    request = dict(original["request"])
    try:
        fresh = await client.chat.completions.create(**request)
    except Exception as exc:
        # A replay that could not be issued is not a reproducibility result, and must not be
        # counted as one. Recording a full cycle exhausts this key's tokens-per-minute
        # budget, so replaying it immediately afterwards hits a 429 routinely.
        return {"decision_id": did, "status": "replay_failed",
                "detail": f"{type(exc).__name__}: {exc}",
                "recorded_at": original.get("ts"), "model": original.get("model"),
                "role": original.get("role"), "temperature": request.get("temperature"),
                "seed": request.get("seed"),
                "system_fingerprint_recorded": original.get("system_fingerprint")}

    old_text, old_calls = _extract(original.get("response"))
    new_text, new_calls = _extract(fresh)

    if old_text == new_text and old_calls == new_calls:
        status = "exact"
    elif old_calls == new_calls:
        # Same action, different words. This is the honest target -- see the module docstring.
        status = "equivalent"
    else:
        status = "divergent"

    old_fp = original.get("system_fingerprint")
    new_fp = getattr(fresh, "system_fingerprint", None)
    return {
        "decision_id": did,
        "status": status,
        "recorded_at": original.get("ts"),
        "replayed_at": datetime.now(timezone.utc).isoformat(),
        "model": original.get("model"),
        "role": original.get("role"),
        "temperature": request.get("temperature"),
        "seed": request.get("seed"),
        "system_fingerprint_recorded": old_fp,
        "system_fingerprint_now": new_fp,
        # A fingerprint change means the backend moved. Even an exact match across one is
        # luck rather than evidence, and a divergence across one is expected, not a bug.
        "fingerprint_changed": bool(old_fp and new_fp and old_fp != new_fp),
        "recorded_tool_calls": old_calls,
        "replayed_tool_calls": new_calls,
        "recorded_text": old_text[:500],
        "replayed_text": new_text[:500],
    }


def _wilson(successes: int, n: int, z: float = 1.96) -> tuple:
    """Wilson score interval for a proportion.

    Wilson rather than the normal approximation on purpose: at these sample sizes and with a
    rate that may sit near 0 or 1, the normal interval runs past the [0,1] bounds and reads
    as more precise than the data supports.
    """
    if n == 0:
        return (None, None)
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def _tools_only(calls: list) -> list:
    """Just the tool names, so a divergence that changed WHICH tool is called can be told
    apart from one that only changed the arguments. The first is an action change; the
    second may be cosmetic."""
    return [name for name, _args in calls]


async def replay_many(limit: int = 5, path: str = None, repeats: int = 1) -> dict:
    """Replay the most recent `limit` distinct decisions and write a report.

    A replay only re-issues the request to the model. It never executes what comes back --
    which matters more than it sounds, because a replayed response has already been observed
    asking to place an order where the recorded one only read a chain.
    """
    path = path or os.path.join(CONFIG.logs_dir, "replay_report.json")
    seen, distinct = set(), []
    for r in reversed(load_calls()):
        did = r.get("decision_id")
        if did and did not in seen:
            seen.add(did)
            distinct.append(did)
        if len(distinct) >= limit:
            break

    # With fewer distinct decisions than replays wanted, cycle through them. Replaying one
    # fixed input repeatedly is the more direct test of the claim anyway: the question is
    # whether identical inputs give identical outputs, and that needs repeated trials on the
    # same input, not one trial each on many.
    ids = [distinct[i % len(distinct)] for i in range(limit * repeats)] if distinct else []

    results = []
    for i, did in enumerate(ids):
        if i:
            # This key's TPM budget is the binding constraint, not the API's rate limiter:
            # each of these requests carries the full tool schemas. Space them out.
            await asyncio.sleep(RETRY_SPACING_SECONDS)
        r = await replay(did)
        if r["status"] == "replay_failed" and "RateLimit" in (r.get("detail") or ""):
            await asyncio.sleep(RETRY_SPACING_SECONDS * 2)
            r = await replay(did)
        results.append(r)
    counted = [r for r in results if r["status"] in ("exact", "equivalent", "divergent")]
    divergent = [r for r in counted if r["status"] == "divergent"]
    # A divergence that changed WHICH tool is called is an action change. One that kept the
    # same tools and altered only their arguments is a weaker result and is counted apart.
    tool_changed = [r for r in divergent
                    if _tools_only(r["recorded_tool_calls"]) != _tools_only(r["replayed_tool_calls"])]
    n = len(counted)
    lo, hi = _wilson(len(divergent), n)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "replays": n,
        "distinct_decisions_replayed": len(set(ids)),
        "repeats_per_decision": repeats,
        "exact": sum(1 for r in counted if r["status"] == "exact"),
        "equivalent": sum(1 for r in counted if r["status"] == "equivalent"),
        "divergent": len(divergent),
        "divergence_rate": round(len(divergent) / n, 4) if n else None,
        "divergence_rate_ci95": {"lower": lo, "upper": hi, "method": "Wilson score"},
        "divergent_tool_changed": len(tool_changed),
        "divergent_args_only": len(divergent) - len(tool_changed),
        "failed_to_replay": sum(1 for r in results if r["status"] == "replay_failed"),
        "across_fingerprint_change": sum(1 for r in counted if r["fingerprint_changed"]),
        "conditions": ("temperature 0, fixed seed, same model -- the conditions under which "
                       "OpenAI's best-effort determinism is supposed to hold"),
        "reproducibility": summary()["reproducibility"],
        "results": results,
    }
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    return report


def summary() -> dict:
    """What has been recorded, for the dashboard and for `--replay list`."""
    rows = load_calls()
    return {
        "calls_recorded": len(rows),
        "distinct_decisions": len({r.get("decision_id") for r in rows}),
        "log": _path() if rows else None,
        # Stated rather than implied: this is the tier we actually reach.
        "reproducibility": ("inputs fully recorded and re-runnable; not bitwise "
                            "deterministic -- OpenAI's seed is best-effort and holds only "
                            "within one system_fingerprint"),
        "calls": [{
            "decision_id": r.get("decision_id"),
            "ts": r.get("ts"),
            "provider": r.get("provider"),
            "model": r.get("model"),
            "role": r.get("role"),
            "temperature": r.get("temperature"),
            "seed": r.get("seed"),
            "system_fingerprint": r.get("system_fingerprint"),
            "finish_reason": r.get("finish_reason"),
            "cost_usd": r.get("cost_usd"),
        } for r in rows],
    }


def demo() -> None:
    """Self-check: ids are content-derived, and the three outcomes classify correctly."""
    req = {"model": "gpt-4o-mini", "temperature": 0, "seed": 42,
           "messages": [{"role": "user", "content": "hello"}]}
    assert decision_id(req) == decision_id(dict(reversed(list(req.items())))), \
        "decision_id must not depend on key order"
    assert decision_id(req) != decision_id({**req, "temperature": 1}), \
        "a different temperature is a different decision"
    print(f"decision_id is content-derived and order-independent: {decision_id(req)}")

    def resp(text, tool=None, args=None):
        msg = {"content": text}
        if tool:
            msg["tool_calls"] = [{"function": {"name": tool, "arguments": args}}]
        return {"choices": [{"message": msg, "finish_reason": "stop"}]}

    a = resp("buying SPY", "place_option_order", '{"symbol":"SPY","qty":1}')
    same_args_diff_order = resp("buying SPY", "place_option_order", '{"qty":1,"symbol":"SPY"}')
    diff_prose = resp("I will buy SPY", "place_option_order", '{"symbol":"SPY","qty":1}')
    diff_action = resp("buying QQQ", "place_option_order", '{"symbol":"QQQ","qty":1}')

    ta, ca = _extract(a)
    assert ca == _extract(same_args_diff_order)[1], "argument key order must not matter"
    assert (ta, ca) == _extract(a), "extraction must be stable"
    assert ca != _extract(diff_action)[1]
    assert ca == _extract(diff_prose)[1] and ta != _extract(diff_prose)[0]
    print("classification: identical -> exact, same call different prose -> equivalent, "
          "different call -> divergent")

    assert find_call("nosuchid00") is None
    print("missing decision_id -> not_found, no exception")
    print("replay: all checks pass")


if __name__ == "__main__":
    demo()

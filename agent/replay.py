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

    # Route by provider. Both are OpenAI-wire-compatible, so the same client re-issues
    # either -- what differs is the key and the base URL. Before this, a recorded Featherless
    # call was "unsupported" and the arbiter could never enter the determinism pool.
    provider = original.get("provider")
    if provider == "openai":
        key, base_url, host = CONFIG.openai_api_key, None, "api.openai.com"
        key_name = "OPENAI_API_KEY"
    elif provider == "featherless":
        from agent.arbiter import ARBITER_BASE_URL
        key = os.environ.get("FEATHERLESS_API_KEY", "").strip()
        base_url, host = ARBITER_BASE_URL, "api.featherless.ai"
        key_name = "FEATHERLESS_API_KEY"
    else:
        return {"decision_id": did, "status": "unsupported",
                "detail": f"no replay route for provider {provider!r}"}
    if not key:
        return {"decision_id": did, "status": "no_credentials",
                "detail": f"{key_name} is not set; cannot re-issue the request"}

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=key, **({"base_url": base_url} if base_url else {}))
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
                "role": original.get("role"), "provider": provider,
                "temperature": request.get("temperature"),
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
        "provider": provider,
        "provider_host": host,
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


# --- stratified measurement --------------------------------------------------

# Turns where the model is DECIDING rather than researching. A divergence here changes what
# the system would do; a divergence in a read changes only how it got there.
DECISION_TOOLS = {"propose_trade", "review_decision"}

# Per-cell analysis rules, fixed BEFORE the run so nothing is chosen after seeing results.
CELL_RULES = {
    ("openai", "gpt-4o-mini", "proposer"): {
        "quotable": True, "caveat": None, "measure": "decision_changed"},
    ("openai", "gpt-4o", "critic"): {
        "quotable": True, "measure": "decision_changed",
        "caveat": ("tool_choice is FORCED to review_decision, so this cell's output space is "
                   "constrained by construction. Its rate is not comparable to a free-choice "
                   "turn and must never be pooled with one.")},
    ("openai", "gpt-4o-mini", "single_agent"): {
        "quotable": True, "measure": "decision_changed",
        "caveat": ("11 unique decisions replayed ~5.5x each: this measures same-input "
                   "determinism, not conversation diversity.")},
    ("featherless", "Qwen/Qwen2.5-7B-Instruct", "arbiter"): {
        "quotable": False, "measure": "ruling_changed",
        "caveat": ("only 4 unique decisions at ~15x repeats, and the arbiter emits JSON text "
                   "rather than a tool call. This answers 'is Featherless deterministic on a "
                   "fixed input' and is NOT a model comparison.")},
}


def _decision_calls(calls: list) -> list:
    return [(n, a) for n, a in calls if n in DECISION_TOOLS]


def _spacing_for(avg_input_tokens: float) -> float:
    """Seconds between replays so a cell stays under a 200k tokens-per-minute ceiling.

    Each replay re-sends the whole recorded conversation, so a 57k-token single-agent turn
    permits only ~3.5 replays a minute. Pacing by the cell's own size beats one global sleep:
    the critic's 1k-token turns would otherwise wait as long as the largest cell.
    """
    if avg_input_tokens <= 0:
        return 2.0
    per_minute = max(1.0, 180_000 / avg_input_tokens)   # 180k, not 200k, leaves headroom
    return max(2.0, 60.0 / per_minute)


async def replay_stratified(n_per_cell: int = 60, path: str = None) -> dict:
    """Replay n_per_cell times in each (provider, model, role) cell and report per cell.

    Pooling across cells was the flaw in the previous measurement: 31 of 40 replays were one
    model in one role, so a single figure described that cell and was presented as the
    pipeline. This fixes the sampling rather than the presentation.
    """
    path = path or os.path.join(CONFIG.logs_dir, "replay_stratified.json")
    calls = load_calls()

    cells = {}
    for c in calls:
        key = (c.get("provider"), c.get("model"), c.get("role"))
        cell = cells.setdefault(key, {"ids": [], "in_tok": []})
        if c["decision_id"] not in cell["ids"]:
            cell["ids"].append(c["decision_id"])
        u = (c.get("response") or {}).get("usage") or {}
        if u.get("prompt_tokens"):
            cell["in_tok"].append(u["prompt_tokens"])

    out_cells = []
    for key, inv in sorted(cells.items(), key=lambda kv: str(kv[0])):
        provider, model, role = key
        ids = inv["ids"]
        if not ids:
            continue
        avg_in = sum(inv["in_tok"]) / len(inv["in_tok"]) if inv["in_tok"] else 0
        spacing = _spacing_for(avg_in)
        rules = CELL_RULES.get(key, {"quotable": False, "measure": "decision_changed",
                                     "caveat": "no pre-registered rule for this cell"})
        print(f"\n[{provider}/{model}/{role}] {n_per_cell} replays over {len(ids)} unique "
              f"decisions, {spacing:.0f}s spacing, avg {avg_in:,.0f} input tokens")

        results = []
        for i in range(n_per_cell):
            if i:
                await asyncio.sleep(spacing)
            did = ids[i % len(ids)]
            r = await replay(did)
            if r["status"] == "replay_failed" and "RateLimit" in (r.get("detail") or ""):
                await asyncio.sleep(spacing * 2)
                r = await replay(did)
            results.append(r)
            if (i + 1) % 10 == 0:
                done = [x for x in results if x["status"] in ("exact", "equivalent", "divergent")]
                dv = sum(1 for x in done if x["status"] == "divergent")
                print(f"    {i+1}/{n_per_cell}  counted={len(done)} divergent={dv}", flush=True)

        counted = [r for r in results if r["status"] in ("exact", "equivalent", "divergent")]
        div = [r for r in counted if r["status"] == "divergent"]
        lo, hi = _wilson(len(div), len(counted))

        # Decision-tool subset: turns where the model was actually deciding.
        dec_turns, dec_changed = [], []
        for r in counted:
            old_d = _decision_calls(r.get("recorded_tool_calls") or [])
            new_d = _decision_calls(r.get("replayed_tool_calls") or [])
            if old_d or new_d:
                dec_turns.append(r)
                if old_d != new_d:
                    dec_changed.append(r)
        dlo, dhi = _wilson(len(dec_changed), len(dec_turns))

        # Arbiter: the ruling is JSON text, not a tool call, so it needs its own measure.
        rul_turns, rul_changed = [], []
        if rules["measure"] == "ruling_changed":
            from agent.arbiter import _parse_ruling
            for r in counted:
                a = _parse_ruling(r.get("recorded_text") or "")["ruling"]
                b = _parse_ruling(r.get("replayed_text") or "")["ruling"]
                rul_turns.append(r)
                if a != b:
                    rul_changed.append(r)
        rlo, rhi = _wilson(len(rul_changed), len(rul_turns))

        out_cells.append({
            "provider": provider, "model": model, "role": role,
            "unique_decisions": len(ids),
            "repeats_per_decision": round(n_per_cell / len(ids), 2),
            "avg_input_tokens": round(avg_in),
            "replays_attempted": n_per_cell,
            "replays_counted": len(counted),
            "failed_to_replay": len(results) - len(counted),
            "exact": sum(1 for r in counted if r["status"] == "exact"),
            "equivalent": sum(1 for r in counted if r["status"] == "equivalent"),
            "divergent": len(div),
            "divergence_rate": round(len(div) / len(counted), 4) if counted else None,
            "divergence_rate_ci95": {"lower": lo, "upper": hi, "method": "Wilson score"},
            "decision_turns": len(dec_turns),
            "decision_changed": len(dec_changed),
            "decision_changed_rate": (round(len(dec_changed) / len(dec_turns), 4)
                                       if dec_turns else None),
            "decision_changed_ci95": {"lower": dlo, "upper": dhi, "method": "Wilson score"},
            "ruling_turns": len(rul_turns) or None,
            "ruling_changed": len(rul_changed) if rul_turns else None,
            "ruling_changed_rate": (round(len(rul_changed) / len(rul_turns), 4)
                                     if rul_turns else None),
            "ruling_changed_ci95": ({"lower": rlo, "upper": rhi, "method": "Wilson score"}
                                     if rul_turns else None),
            # "divergent" requires the tool calls to differ. A responder that emits no tool
            # calls can never reach it, so divergence_rate is meaningless for the arbiter and
            # the honest measures are ruling_changed and wording_changed.
            "divergence_rate_meaningful": bool(
                any((r.get("recorded_tool_calls") or r.get("replayed_tool_calls"))
                    for r in counted)),
            "wording_changed": sum(1 for r in counted if r["status"] == "equivalent"),
            "wording_changed_rate": (round(
                sum(1 for r in counted if r["status"] == "equivalent") / len(counted), 4)
                if counted else None),
            "primary_measure": rules["measure"],
            "quotable": rules["quotable"],
            "caveat": rules["caveat"],
            "across_fingerprint_change": sum(1 for r in counted if r.get("fingerprint_changed")),
            "results": [{k: v for k, v in r.items()
                          if k not in ("recorded_text", "replayed_text")} for r in results],
        })

    # Decision-tool rate across the cells whose measure is decision_changed. This is the
    # headline: it is a like-for-like question asked of every free-choice cell.
    # Reported PER CELL, never pooled. The first version of this summed the critic and the
    # proposer into one 99/100 figure -- and the critic runs with tool_choice forced, so that
    # pooled a constrained cell with a free-choice one, which is exactly what the
    # pre-registration forbade. Caught before publication; the pooled field is gone rather
    # than kept with a footnote.
    dec_cells = [c for c in out_cells if c["primary_measure"] == "decision_changed"
                 and c["decision_turns"]]

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_per_cell": n_per_cell,
        "pre_registered": ("cells, quotability and per-cell measures were fixed in "
                           "agent/replay.py CELL_RULES before this run was executed"),
        "conditions": "temperature 0, fixed seed where the provider supports one, same model",
        "headline": {
            "metric": "decision-tool divergence: did the DECISION change on replay",
            "reported": "per cell only — see note",
            "note": ("NOT pooled. The critic runs with tool_choice forced, so its output space "
                      "is constrained by construction and its rate is not comparable to a "
                      "free-choice turn. The arbiter emits JSON text rather than a tool call "
                      "and is measured separately as ruling_changed."),
            "cells": [{
                "cell": f"{c['provider']}/{c['model']}/{c['role']}",
                "free_choice": c["role"] != "critic",
                "decision_turns": c["decision_turns"],
                "decision_changed": c["decision_changed"],
                "rate": c["decision_changed_rate"],
                "ci95": c["decision_changed_ci95"],
            } for c in dec_cells],
        },
        "cells": out_cells,
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

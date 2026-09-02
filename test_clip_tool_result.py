"""Tool results fed to a model must be bounded; results fed to a parser must not be.

A cycle died live on 149,721 tokens after a handful of option-chain reads, because every
tool result was appended to the conversation whole. The fix has to bound what the model
sees without touching what the deterministic code parses -- a silently clipped chain is
worse than a large one.

    python test_clip_tool_result.py
"""
import json

from agent.mcp_parsers import clip_tool_result, PROMPT_RESULT_CHAR_LIMIT, parse_option_chain_snapshot


def _fake_chain(n: int) -> str:
    snaps = {
        f"SPY260904P{int((700 + i) * 1000):08d}": {
            "latestQuote": {"bp": 1.0 + i / 100, "ap": 1.1 + i / 100},
            "greeks": {"delta": -0.3}, "impliedVolatility": 0.2,
        }
        for i in range(n)
    }
    return json.dumps({"_alpaca_mcp_security": {"trust": "untrusted_tool_output"},
                       "data": {"snapshots": snaps}})


def demo() -> None:
    small = '{"data": {"result": []}}'
    assert clip_tool_result(small) is small, "a small result must pass through untouched"
    assert clip_tool_result(None) is None

    big = _fake_chain(4000)
    assert len(big) > PROMPT_RESULT_CHAR_LIMIT * 3, len(big)
    clipped = clip_tool_result(big)
    assert len(clipped) < len(big)
    assert clipped.startswith(big[:1000]), "must keep the head, envelope included"
    assert "TRUNCATED" in clipped and "narrower" in clipped, \
        "must tell the model what happened and what to do instead"
    print(f"chain result {len(big):,} chars -> {len(clipped):,} chars fed to the model")

    # 25 clipped results must fit a 128K-token window alongside ~21K tokens of tool schemas.
    worst_case_tokens = 25 * len(clipped) // 4 + 21_000
    assert worst_case_tokens < 128_000, f"{worst_case_tokens:,} tokens still overruns the window"
    print(f"25 tool calls worst case ~{worst_case_tokens:,} tokens, inside a 128,000 window")

    # The parsing path must never see a clipped string: prove the clipped one is unusable, so
    # nobody is tempted to route parsers through it.
    assert len(parse_option_chain_snapshot(big)) == 4000
    try:
        parse_option_chain_snapshot(clipped)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    else:
        raise AssertionError("clipped JSON parsed successfully; the separation isn't being tested")
    print("full result parses to 4,000 quotes; clipped result does not parse at all")

    print("clip_tool_result: all checks pass")


if __name__ == "__main__":
    demo()

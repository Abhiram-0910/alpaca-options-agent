"""Featherless arbiter — a third-seat model that rules when Proposer and Critic disagree.

Architecture constraints (non-negotiable):
  - No tools, no MCP access, no order-placing capability whatsoever.
  - Reads the Proposer's proposal and the Critic's concerns and issues a structured ruling.
  - Its ruling is advisory: the deterministic RiskGate still holds final authority.
  - Verdict + rationale are appended to the trade log for the audit record.
  - If Featherless is unconfigured (FEATHERLESS_API_KEY absent) the function raises
    ArbiterUnavailable and the caller must decide how to handle the deadlock.

Wiring note (for multi_agent.py):
  Call `arbitrate()` when the Critic issues `reject` on a proposal that the Proposer
  submitted with action="trade". On a Critic approval or a Proposer skip, the arbiter
  is not invoked — it exists only to resolve genuine disagreement.

  The caller reads `ArbiterRuling.ruling`:
    "proceed"  → arbiter sides with Proposer; execution still goes through RiskGate.
    "abandon"  → arbiter sides with Critic; cycle ends without an order.
    "deadlock" → arbiter could not reach a clear verdict; caller should abandon.

Model selection:
  We default to `meta-llama/Llama-3.1-8B-Instruct` — a compact, instruction-tuned model
  available on the free Featherless tier. It has no financial fine-tuning and is not
  authoritative on options strategy; that is intentional. Its role is architectural
  (independent seat) not oracular. The RiskGate remains the authority on risk.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from openai import AsyncOpenAI

from agent.trade_log import log_event

# ── model ──────────────────────────────────────────────────────────────────────
# Default to a compact but capable instruction model available on Featherless free tier.
# Override via FEATHERLESS_MODEL env var.
DEFAULT_ARBITER_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
ARBITER_BASE_URL = "https://api.featherless.ai/v1"

# Context budget: keep the arbiter prompt small — it has no tools and sees only the
# structured arguments, not raw chain data. This bounds cost per cycle.
MAX_ARBITER_TOKENS = 512


class ArbiterUnavailable(RuntimeError):
    """Raised when FEATHERLESS_API_KEY is absent or the call fails non-retryably."""


@dataclass
class ArbiterRuling:
    ruling: str            # "proceed" | "abandon" | "deadlock"
    rationale: str
    model: str
    latency_ms: int
    raw_response: Optional[str] = None
    error: Optional[str] = None


# ── prompt construction ────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    return (
        "You are an independent ARBITER in an options-trading pipeline. "
        "A Proposer agent proposed a trade. A Critic agent rejected it. "
        "You have NO tools, NO ability to place orders, and NO access to live market data. "
        "Your sole function is to read both arguments and the validation evidence and rule on "
        "whether the Critic's veto should stand.\n\n"
        "Rules you must follow:\n"
        "1. If the Critic identified a factual error in the proposal (wrong symbol, "
        "   unvalidated strategy, risk-cap violation), rule ABANDON.\n"
        "2. If the Critic's rejection is a matter of opinion or preference and the Proposer's "
        "   rationale cites real backtest evidence, rule PROCEED — but only if the strategy is "
        "   listed as validated.\n"
        "3. If you cannot determine which side is correct, or validation evidence is absent, "
        "   rule DEADLOCK. A deadlock resolves as an abandon.\n"
        "4. Never invent market data or backtest numbers. Only evaluate the arguments as given.\n\n"
        "Respond ONLY with a JSON object in this exact format:\n"
        '{"ruling": "proceed"|"abandon"|"deadlock", "rationale": "<one concise sentence>"}'
    )


def _build_user_prompt(
    proposal: dict,
    critic_concerns: list[str],
    critic_rationale: str,
    validation_summary: str,
) -> str:
    return (
        f"VALIDATION EVIDENCE:\n{validation_summary}\n\n"
        f"PROPOSAL:\n{json.dumps(proposal, indent=2)}\n\n"
        f"CRITIC CONCERNS:\n"
        + "\n".join(f"- {c}" for c in (critic_concerns or ["(none listed)"]))
        + f"\n\nCRITIC RATIONALE:\n{critic_rationale}\n\n"
        "Rule on whether the Critic's veto should stand."
    )


# ── main entry point ───────────────────────────────────────────────────────────

async def arbitrate(
    *,
    proposal: dict,
    critic_concerns: list[str],
    critic_rationale: str,
    validation_summary: str,
    cycle_id: str | None = None,
) -> ArbiterRuling:
    """
    Call the Featherless arbiter to resolve a Proposer/Critic disagreement.

    Parameters
    ----------
    proposal          : The full propose_trade input dict from the Proposer.
    critic_concerns   : The list of concerns from the Critic's review_decision call.
    critic_rationale  : The Critic's prose rationale.
    validation_summary: Plain-text summary of backtest validation outcomes (from
                        agent.backtest_evidence.load_backtest_summary).
    cycle_id          : Optional string identifier for the current trading cycle,
                        used to correlate the audit log entry.

    Returns
    -------
    ArbiterRuling with ruling in {"proceed", "abandon", "deadlock"}.

    Raises
    ------
    ArbiterUnavailable if FEATHERLESS_API_KEY is unset or the API returns a
    non-retryable error.
    """
    api_key = os.environ.get("FEATHERLESS_API_KEY", "").strip()
    if not api_key:
        raise ArbiterUnavailable(
            "FEATHERLESS_API_KEY is not set; arbiter cannot be invoked."
        )

    model = os.environ.get("FEATHERLESS_MODEL", DEFAULT_ARBITER_MODEL)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=ARBITER_BASE_URL,
    )

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(
        proposal=proposal,
        critic_concerns=critic_concerns,
        critic_rationale=critic_rationale,
        validation_summary=validation_summary,
    )

    t0 = time.monotonic()
    ruling = "deadlock"
    rationale = "Arbiter could not parse a valid ruling from the model response."
    raw_text: str | None = None
    error: str | None = None

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=MAX_ARBITER_TOKENS,
            temperature=0.0,
        )
        raw_text = response.choices[0].message.content or ""
        parsed = _parse_ruling(raw_text)
        ruling = parsed["ruling"]
        rationale = parsed["rationale"]
    except ArbiterUnavailable:
        raise
    except Exception as exc:
        error = str(exc)
        ruling = "deadlock"
        rationale = f"Arbiter call failed: {error}"

    latency_ms = int((time.monotonic() - t0) * 1000)

    result = ArbiterRuling(
        ruling=ruling,
        rationale=rationale,
        model=model,
        latency_ms=latency_ms,
        raw_response=raw_text,
        error=error,
    )

    # Append to the audit log regardless of outcome.
    # log_event's signature is log_event(event_type, **fields). This was passing a positional
    # dict, which raises TypeError -- and it would have raised at the only moment the arbiter
    # is ever invoked, i.e. the first genuine Proposer/Critic disagreement.
    log_event(
        "arbiter_ruling",
        cycle_id=cycle_id,
        ruling=ruling,
        rationale=rationale,
        model=model,
        latency_ms=latency_ms,
        proposal_action=proposal.get("action"),
        proposal_symbol=proposal.get("symbol"),
        proposal_strategy=proposal.get("strategy"),
        error=error,
    )

    return result


# ── response parsing ───────────────────────────────────────────────────────────

def _parse_ruling(text: str) -> dict:
    """
    Extract {"ruling": ..., "rationale": ...} from the model response.
    Handles responses where the model wraps the JSON in markdown code fences
    or adds prose before/after the JSON block.
    """
    VALID_RULINGS = {"proceed", "abandon", "deadlock"}

    # 1. Try direct JSON parse.
    try:
        obj = json.loads(text.strip())
        r = _validate_ruling_obj(obj, VALID_RULINGS)
        if r:
            return r
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Extract from a ```json ... ``` fence.
    import re
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            obj = json.loads(fence_match.group(1))
            r = _validate_ruling_obj(obj, VALID_RULINGS)
            if r:
                return r
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. Find any {...} blob in the text.
    brace_match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if brace_match:
        try:
            obj = json.loads(brace_match.group(0))
            r = _validate_ruling_obj(obj, VALID_RULINGS)
            if r:
                return r
        except (json.JSONDecodeError, ValueError):
            pass

    # 4. No keyword fallback. This used to rule "proceed" whenever that word appeared
    #    anywhere in the response, and checked it BEFORE "abandon" -- while the arbiter's own
    #    user prompt embeds the Critic's rationale verbatim, so any text that can reach the
    #    Critic could reach this substring search and flip the ruling by saying the word.
    #    A response we cannot parse structurally is one we do not understand, and the only
    #    safe reading of that is deadlock, which resolves as abandon.
    return {
        "ruling": "deadlock",
        "rationale": f"Could not parse a structured ruling from the arbiter response: {text[:200]}",
    }


def _validate_ruling_obj(obj: dict, valid: set) -> dict | None:
    if not isinstance(obj, dict):
        return None
    ruling = obj.get("ruling", "").lower()
    if ruling not in valid:
        return None
    return {"ruling": ruling, "rationale": str(obj.get("rationale", ""))}

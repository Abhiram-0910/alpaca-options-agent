"""Tests for agent/arbiter.py — the Featherless third-seat arbiter.

These tests cover:
  1. _parse_ruling() with clean JSON, fenced JSON, prose fallback, and garbage.
  2. ArbiterUnavailable raised when FEATHERLESS_API_KEY is absent.
  3. arbitrate() with a mocked AsyncOpenAI client — verifies audit log output and
     that the ruling is correctly extracted.
  4. Deadlock on API failure.

Run with: python -m pytest test_arbiter.py -v
"""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.arbiter import (
    ArbiterRuling,
    ArbiterUnavailable,
    _parse_ruling,
    arbitrate,
)


# ── _parse_ruling unit tests ───────────────────────────────────────────────────

class TestParseRuling:
    def test_clean_json_proceed(self):
        text = '{"ruling": "proceed", "rationale": "Proposal cites validated backtest."}'
        result = _parse_ruling(text)
        assert result["ruling"] == "proceed"
        assert "backtest" in result["rationale"]

    def test_clean_json_abandon(self):
        text = '{"ruling": "abandon", "rationale": "Strategy not validated for symbol."}'
        result = _parse_ruling(text)
        assert result["ruling"] == "abandon"

    def test_clean_json_deadlock(self):
        text = '{"ruling": "deadlock", "rationale": "Insufficient evidence either way."}'
        result = _parse_ruling(text)
        assert result["ruling"] == "deadlock"

    def test_fenced_json(self):
        text = '```json\n{"ruling": "abandon", "rationale": "Risk cap exceeded."}\n```'
        result = _parse_ruling(text)
        assert result["ruling"] == "abandon"

    def test_fenced_no_language_tag(self):
        text = '```\n{"ruling": "proceed", "rationale": "Valid."}\n```'
        result = _parse_ruling(text)
        assert result["ruling"] == "proceed"

    def test_json_embedded_in_prose(self):
        text = 'After careful review: {"ruling": "abandon", "rationale": "Bad."} That is my verdict.'
        result = _parse_ruling(text)
        assert result["ruling"] == "abandon"

    def test_keyword_fallback_proceed(self):
        text = "I think we should proceed with this trade given the evidence."
        result = _parse_ruling(text)
        assert result["ruling"] == "proceed"

    def test_keyword_fallback_abandon(self):
        text = "We must abandon this trade immediately."
        result = _parse_ruling(text)
        assert result["ruling"] == "abandon"

    def test_garbage_returns_deadlock(self):
        text = "Lorem ipsum dolor sit amet."
        result = _parse_ruling(text)
        assert result["ruling"] == "deadlock"

    def test_invalid_ruling_value_falls_through(self):
        text = '{"ruling": "maybe", "rationale": "Not sure."}'
        result = _parse_ruling(text)
        assert result["ruling"] == "deadlock"

    def test_empty_string_returns_deadlock(self):
        result = _parse_ruling("")
        assert result["ruling"] == "deadlock"


# ── ArbiterUnavailable when key absent ────────────────────────────────────────

@pytest.mark.asyncio
async def test_arbiter_unavailable_when_no_key():
    """arbitrate() must raise ArbiterUnavailable if FEATHERLESS_API_KEY is not set."""
    env_without_key = {k: v for k, v in os.environ.items() if k != "FEATHERLESS_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        with pytest.raises(ArbiterUnavailable, match="FEATHERLESS_API_KEY"):
            await arbitrate(
                proposal={"action": "trade", "symbol": "SPY", "strategy": "vertical_credit_spread"},
                critic_concerns=["No backtest evidence cited."],
                critic_rationale="The proposal lacks backtest support.",
                validation_summary="SPY vertical_credit_spread: FAILED",
            )


# ── arbitrate() with mocked OpenAI client ─────────────────────────────────────

def _make_mock_response(ruling: str, rationale: str):
    """Build a mock openai ChatCompletion response."""
    content = json.dumps({"ruling": ruling, "rationale": rationale})
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.mark.asyncio
async def test_arbitrate_abandon(tmp_path, monkeypatch):
    """Happy path: API returns abandon, log_event is called."""
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-key")
    monkeypatch.setenv("FEATHERLESS_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

    logged_events = []

    mock_response = _make_mock_response("abandon", "Critic correctly identified missing validation.")

    with patch("agent.arbiter.AsyncOpenAI") as MockClient, \
         patch("agent.arbiter.log_event", side_effect=lambda *a, **kw: logged_events.append((a, kw))):

        mock_create = AsyncMock(return_value=mock_response)
        MockClient.return_value.chat.completions.create = mock_create

        result = await arbitrate(
            proposal={"action": "trade", "symbol": "MSFT", "strategy": "cash_secured_put",
                       "rationale": "Strong IV."},
            critic_concerns=["MSFT never cleared the validation gate."],
            critic_rationale="No backtest evidence exists for this symbol.",
            validation_summary="MSFT: no primary validation records.",
            cycle_id="test-cycle-001",
        )

    assert isinstance(result, ArbiterRuling)
    assert result.ruling == "abandon"
    assert "Critic correctly" in result.rationale
    assert result.error is None

    # Audit log must have been written.
    assert len(logged_events) == 1
    event_type, event_data = logged_events[0][0]
    assert event_type == "arbiter_ruling"
    assert event_data["ruling"] == "abandon"
    assert event_data["cycle_id"] == "test-cycle-001"


@pytest.mark.asyncio
async def test_arbitrate_proceed(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-key")

    mock_response = _make_mock_response("proceed", "Proposal cites validated backtest for IWM covered_call.")

    with patch("agent.arbiter.AsyncOpenAI") as MockClient, \
         patch("agent.arbiter.log_event"):

        MockClient.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await arbitrate(
            proposal={"action": "trade", "symbol": "IWM", "strategy": "covered_call",
                       "rationale": "IWM covered_call passed primary gate."},
            critic_concerns=["Earnings risk not discussed."],
            critic_rationale="Consider the earnings calendar.",
            validation_summary="IWM covered_call: PASSED primary gate (but failed sub-period stability).",
        )

    assert result.ruling == "proceed"


@pytest.mark.asyncio
async def test_arbitrate_api_failure_returns_deadlock(monkeypatch):
    """When the API call raises, the arbiter must return deadlock (not raise)."""
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-key")

    with patch("agent.arbiter.AsyncOpenAI") as MockClient, \
         patch("agent.arbiter.log_event"):

        MockClient.return_value.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("Connection timeout")
        )

        result = await arbitrate(
            proposal={"action": "trade", "symbol": "SPY", "strategy": "iron_condor"},
            critic_concerns=["Volatility risk."],
            critic_rationale="IV crush risk is high.",
            validation_summary="SPY iron_condor: FAILED",
        )

    assert result.ruling == "deadlock"
    assert result.error is not None
    assert "Connection timeout" in result.error


@pytest.mark.asyncio
async def test_arbitrate_records_latency(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "test-key")

    mock_response = _make_mock_response("deadlock", "Cannot determine winner.")

    with patch("agent.arbiter.AsyncOpenAI") as MockClient, \
         patch("agent.arbiter.log_event"):

        MockClient.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await arbitrate(
            proposal={"action": "skip", "rationale": "Nothing valid today."},
            critic_concerns=[],
            critic_rationale="Agree with skip.",
            validation_summary="No strategies cleared.",
        )

    assert result.latency_ms >= 0
    assert isinstance(result.latency_ms, int)

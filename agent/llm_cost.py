"""Real, measured Anthropic API cost tracking — shared by every agent that
calls Claude (agent/live_agent.py, agent/multi_agent.py), so cost accounting
stays consistent instead of duplicated per agent.
"""

# $/1M tokens (input, output). Sonnet 5 is this project's default model — the cheapest
# current-generation tier besides Haiku. Extend this if CLAUDE_MODEL is overridden.
PRICING_PER_MTOK = {
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
CACHE_WRITE_MULTIPLIER = 1.25   # cache_creation_input_tokens cost this much of the base input rate
CACHE_READ_MULTIPLIER = 0.10    # cache_read_input_tokens cost this much of the base input rate


def call_cost(usage, model: str) -> float:
    input_rate, output_rate = PRICING_PER_MTOK.get(model, PRICING_PER_MTOK["claude-sonnet-5"])
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    fresh_input = usage.input_tokens
    cost = (
        fresh_input * input_rate
        + cache_write * input_rate * CACHE_WRITE_MULTIPLIER
        + cache_read * input_rate * CACHE_READ_MULTIPLIER
    ) / 1_000_000
    cost += usage.output_tokens * output_rate / 1_000_000
    return cost

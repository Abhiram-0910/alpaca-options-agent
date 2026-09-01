"""Real, measured OpenAI API cost tracking for agent/live_agent_openai.py.

Pricing verified against OpenAI's own pricing page and cross-checked for real,
accessible model IDs against the actual API key before use (not assumed from
training data, which may be stale) — see the session notes for how this was
verified. OpenAI's Chat Completions API caches long, repeated prompt prefixes
automatically server-side (no explicit cache_control breakpoints needed, unlike
Anthropic); `usage.prompt_tokens_details.cached_tokens` reports how much of the
prompt was served from cache on each call.
"""

# $/1M tokens: (input, output, cached_input). Confirmed against openai.platform pricing.
PRICING_PER_MTOK = {
    "gpt-4o-mini": (0.15, 0.60, 0.075),
    "gpt-4.1-mini": (0.40, 1.60, 0.10),
    "gpt-5-mini": (0.25, 2.00, 0.025),
    "o4-mini": (1.10, 4.40, 0.275),
    "gpt-4o": (2.50, 10.00, 1.25),
}


def call_cost(usage, model: str) -> float:
    input_rate, output_rate, cached_rate = PRICING_PER_MTOK.get(model, PRICING_PER_MTOK["gpt-4o-mini"])
    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    details = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = (getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
    fresh_input = max(prompt_tokens - cached_tokens, 0)

    cost = (fresh_input * input_rate + cached_tokens * cached_rate) / 1_000_000
    cost += completion_tokens * output_rate / 1_000_000
    return cost

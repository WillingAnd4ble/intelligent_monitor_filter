"""Per-model token pricing.

Rates expressed as USD per 1M tokens. Update when providers change pricing.
"""

from typing import Dict, NamedTuple


class TokenRate(NamedTuple):
    input_per_million_usd: float
    output_per_million_usd: float


KNOWN_MODELS: Dict[str, TokenRate] = {
    # OpenAI — verify at https://openai.com/api/pricing
    "gpt-4o-mini": TokenRate(0.15, 0.60),
    # Project-defined "gpt-5.4-nano" — adjust when rate-card published
    "gpt-5.4-nano-2026-03-17": TokenRate(0.10, 0.40),
    # Anthropic — verify at https://www.anthropic.com/pricing
    "claude-haiku-4-5-20251001": TokenRate(1.00, 5.00),
}


def compute_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    rate = KNOWN_MODELS[model]
    return (
        tokens_in * rate.input_per_million_usd / 1_000_000
        + tokens_out * rate.output_per_million_usd / 1_000_000
    )

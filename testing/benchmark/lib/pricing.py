"""Per-model token pricing.

Rates expressed as USD per 1M tokens. Update when providers change pricing.
Unknown models return 0.0 instead of raising — this keeps experimental
models (e.g. ad-hoc OpenRouter ids) from crashing the runner. Add an
entry here whenever you want accurate cost reporting for a new model.
"""

import logging
from typing import Dict, NamedTuple

logger = logging.getLogger(__name__)


class TokenRate(NamedTuple):
    input_per_million_usd: float
    output_per_million_usd: float


KNOWN_MODELS: Dict[str, TokenRate] = {
    # OpenAI direct — https://openai.com/api/pricing
    "gpt-4o-mini": TokenRate(0.15, 0.60),
    "gpt-5.4-nano-2026-03-17": TokenRate(0.10, 0.40),
    # Anthropic direct — https://www.anthropic.com/pricing
    "claude-haiku-4-5-20251001": TokenRate(1.00, 5.00),
    # OpenRouter (verify at https://openrouter.ai/models — they vary slightly
    # vs provider-direct pricing because of routing overhead). Add entries
    # for any OpenRouter id you want cost-accurate.
    "openai/gpt-4o-mini": TokenRate(0.15, 0.60),
    "openai/gpt-4o": TokenRate(2.50, 10.00),
    "anthropic/claude-3.5-sonnet": TokenRate(3.00, 15.00),
    "anthropic/claude-3.5-haiku": TokenRate(1.00, 5.00),
    "google/gemini-flash-1.5": TokenRate(0.075, 0.30),
    "meta-llama/llama-3.3-70b-instruct": TokenRate(0.13, 0.40),
    "mistralai/mistral-large": TokenRate(2.00, 6.00),
    "deepseek/deepseek-chat": TokenRate(0.14, 0.28),
    "qwen/qwen-2.5-72b-instruct": TokenRate(0.35, 0.40),
}


def compute_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    rate = KNOWN_MODELS.get(model)
    if rate is None:
        logger.warning(
            "No pricing entry for model %r — reporting cost as $0. "
            "Add it to KNOWN_MODELS in lib/pricing.py for accurate accounting.",
            model,
        )
        return 0.0
    return (
        tokens_in * rate.input_per_million_usd / 1_000_000
        + tokens_out * rate.output_per_million_usd / 1_000_000
    )

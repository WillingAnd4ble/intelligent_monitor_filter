import pytest
from benchmark.lib.pricing import compute_cost_usd, KNOWN_MODELS


def test_known_models_includes_three_targets():
    assert "gpt-4o-mini" in KNOWN_MODELS
    assert "claude-haiku-4-5-20251001" in KNOWN_MODELS
    assert "gpt-5.4-nano-2026-03-17" in KNOWN_MODELS


def test_compute_cost_zero_tokens():
    assert compute_cost_usd("gpt-4o-mini", 0, 0) == 0.0


def test_compute_cost_gpt_4o_mini_one_million_in():
    cost = compute_cost_usd("gpt-4o-mini", 1_000_000, 0)
    assert cost == pytest.approx(0.15, rel=1e-6)


def test_compute_cost_gpt_4o_mini_one_million_out():
    cost = compute_cost_usd("gpt-4o-mini", 0, 1_000_000)
    assert cost == pytest.approx(0.60, rel=1e-6)


def test_compute_cost_unknown_model_returns_zero():
    # Unknown models report 0 (with a logger warning) so experimental
    # OpenRouter ids don't crash the runner — accuracy is opt-in.
    assert compute_cost_usd("nonexistent-model", 100, 50) == 0.0


def test_compute_cost_openrouter_known_model():
    # Spot-check that a curated OpenRouter entry uses its rate.
    cost = compute_cost_usd("anthropic/claude-3.5-sonnet", 1_000_000, 0)
    assert cost == pytest.approx(3.00, rel=1e-6)

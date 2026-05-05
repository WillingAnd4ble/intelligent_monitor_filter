import pytest
from benchmark.lib.metrics import (
    wilson_ci_95, precision_with_ci, pass_through_rates, pearson,
)


def test_wilson_ci_zero_observations():
    lo, hi = wilson_ci_95(0, 0)
    assert lo == 0.0 and hi == 1.0


def test_wilson_ci_perfect():
    lo, hi = wilson_ci_95(10, 10)
    assert hi == pytest.approx(1.0, abs=1e-6)
    assert lo > 0.6


def test_wilson_ci_half():
    lo, hi = wilson_ci_95(5, 10)
    assert lo < 0.5 < hi


def test_precision_with_ci_excludes_borderline():
    p, (lo, hi) = precision_with_ci(tp=3, fp=2)
    assert p == pytest.approx(0.6)
    assert 0 <= lo <= p <= hi <= 1


def test_precision_zero_predictions():
    p, (lo, hi) = precision_with_ci(tp=0, fp=0)
    assert p == 0.0
    assert lo == 0.0 and hi == 1.0


def test_pass_through_basic():
    rates = pass_through_rates(
        before={"evaluator": 30, "critique": 18, "deep_reader": 14},
        after={"evaluator": 18, "critique": 14, "deep_reader": 12},
    )
    assert rates["evaluator"] == pytest.approx(0.6)
    assert rates["critique"] == pytest.approx(14 / 18)
    assert rates["deep_reader"] == pytest.approx(12 / 14)


def test_pearson_perfect_correlation():
    r = pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
    assert r == pytest.approx(1.0)


def test_pearson_zero_variance_returns_none():
    assert pearson([1, 1, 1], [1, 2, 3]) is None

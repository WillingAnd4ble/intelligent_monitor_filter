"""Precision, Wilson 95% CI, pass-through rates, Pearson agreement.

All functions are pure — no I/O, no side effects.
"""

import math
from typing import Dict, List, Optional, Tuple


def wilson_ci_95(successes: int, trials: int) -> Tuple[float, float]:
    """Wilson score 95% CI for a binomial proportion. Stable at extremes."""
    if trials == 0:
        return (0.0, 1.0)
    z = 1.96
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = (z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def precision_with_ci(tp: int, fp: int) -> Tuple[float, Tuple[float, float]]:
    """Precision + Wilson CI. Borderline papers should be excluded *before* calling this."""
    n = tp + fp
    if n == 0:
        return (0.0, (0.0, 1.0))
    return (tp / n, wilson_ci_95(tp, n))


def pass_through_rates(before: Dict[str, int], after: Dict[str, int]) -> Dict[str, float]:
    """survivors_after_node / survivors_before_node, per stage."""
    out: Dict[str, float] = {}
    for stage, b in before.items():
        a = after.get(stage, 0)
        out[stage] = (a / b) if b > 0 else 0.0
    return out


def pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    """Pearson r. Returns None if variance is zero in either series."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def percentile(values: List[float], q: float) -> float:
    """Linear-interpolation percentile, q in [0, 100]. Empty list → 0.0."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = (q / 100.0) * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)

"""Shared statistics for the eval runners."""

from __future__ import annotations

import math


def p95(values) -> float | None:
    """Nearest-rank 95th percentile: the smallest value with at least 95% of the sample at or below it.
    (The earlier index int(0.95 * (n - 1)) returned the minimum for n = 2.)"""
    xs = sorted(values)
    return xs[max(0, math.ceil(0.95 * len(xs)) - 1)] if xs else None

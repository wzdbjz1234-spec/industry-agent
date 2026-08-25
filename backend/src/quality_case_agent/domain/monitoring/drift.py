"""Explainable EWMA/CUSUM/PSI/KS statistics with no heavy runtime dependency."""

from __future__ import annotations

from collections.abc import Sequence
from math import log


def ewma_zscore(value: float, baseline_mean: float, baseline_std: float, *, alpha: float = 0.3) -> float:
    """Return the one-step EWMA deviation in standard-deviation units."""

    scale = max(baseline_std, 1e-6)
    return abs(alpha * (value - baseline_mean) / scale)


def cusum_score(value: float, baseline_mean: float, baseline_std: float, *, slack: float = 0.5) -> float:
    """Return a one-sided upward CUSUM score for process deterioration."""

    scale = max(baseline_std, 1e-6)
    return max(0.0, (value - baseline_mean) / scale - slack)


def population_stability_index(actual: Sequence[float], expected: Sequence[float]) -> float:
    """Calculate PSI for two already aligned histograms."""

    if len(actual) != len(expected) or not actual:
        raise ValueError("PSI histograms must be non-empty and have equal length")
    epsilon = 1e-6
    actual_total = sum(actual) or 1.0
    expected_total = sum(expected) or 1.0
    score = 0.0
    for observed, reference in zip(actual, expected, strict=True):
        observed_ratio = max(observed / actual_total, epsilon)
        reference_ratio = max(reference / expected_total, epsilon)
        score += (observed_ratio - reference_ratio) * log(observed_ratio / reference_ratio)
    return score


def kolmogorov_smirnov_distance(actual: Sequence[float], expected: Sequence[float]) -> float:
    """Calculate the KS distance from aligned histogram bins."""

    if len(actual) != len(expected) or not actual:
        raise ValueError("KS histograms must be non-empty and have equal length")
    actual_total = sum(actual) or 1.0
    expected_total = sum(expected) or 1.0
    actual_cumulative = 0.0
    expected_cumulative = 0.0
    distance = 0.0
    for observed, reference in zip(actual, expected, strict=True):
        actual_cumulative += observed / actual_total
        expected_cumulative += reference / expected_total
        distance = max(distance, abs(actual_cumulative - expected_cumulative))
    return distance

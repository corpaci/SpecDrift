"""Statistics and plotting constants shared by the follow-up --report modes.

Extracted verbatim from the analysis script used for the paper (project commit
6c947fc, semantic-diff-test/analyze.py), so the follow-up reports compute their
intervals and tests exactly as the paper did.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

# Validated categorical palette: all-pairs contrast checked, CVD-safe.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#9b59b6", "#d4a017"]
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#dedcd6"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score interval. NaN for n=0 so an unmeasured cell never plots as 0."""
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def mcnemar_exact(a: np.ndarray, b: np.ndarray) -> tuple[int, int, float]:
    """Exact McNemar on paired binary vectors; returns (b01, b10, p)."""
    b01 = int(((a == 0) & (b == 1)).sum())
    b10 = int(((a == 1) & (b == 0)).sum())
    if b01 + b10 == 0:
        return b01, b10, 1.0
    return b01, b10, float(sps.binomtest(b01, b01 + b10, 0.5).pvalue)


def holm(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values, preserving input order."""
    order = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    adjusted = [0.0] * len(pvalues)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(pvalues) - rank) * pvalues[index])
        adjusted[index] = min(1.0, running)
    return adjusted

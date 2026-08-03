"""Adult-equivalent household portion helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping

AGE_BAND_FACTORS: dict[str, float] = {
    "1-3": 0.35,
    "4-6": 0.50,
    "7-9": 0.65,
    "10-12": 0.80,
}

AGE_BAND_KEYS: tuple[str, ...] = ("1-3", "4-6", "7-9", "10-12")


def ceil_to_half(value: float) -> float:
    """Round up to the next 0.5 (3.15 → 3.5). Exact halves and integers stay put."""
    if value <= 0:
        return 0.0
    return math.ceil(value * 2.0 - 1e-12) / 2.0


def _band_count(bands: Mapping[str, int], key: str) -> int:
    return max(0, int(bands.get(key, 0) or 0))


def age_bands_sum(bands: Mapping[str, int]) -> int:
    return sum(_band_count(bands, key) for key in AGE_BAND_KEYS)


def age_bands_match_children(bands: Mapping[str, int], children_under_13: int) -> bool:
    children = max(0, int(children_under_13 or 0))
    if children == 0:
        return True
    return age_bands_sum(bands) == children


def adult_equivalent_exact(adults: int, bands: Mapping[str, int]) -> float:
    total = float(max(0, int(adults or 0)))
    for key, factor in AGE_BAND_FACTORS.items():
        total += _band_count(bands, key) * factor
    return total


def adult_equivalent_servings(adults: int, bands: Mapping[str, int]) -> float:
    return ceil_to_half(adult_equivalent_exact(adults, bands))

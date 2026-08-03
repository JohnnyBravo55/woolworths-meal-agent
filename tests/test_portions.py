"""Tests for adult-equivalent portion helpers."""

from shared.portions import (
    adult_equivalent_exact,
    adult_equivalent_servings,
    age_bands_match_children,
    ceil_to_half,
)


def test_ceil_to_half():
    assert ceil_to_half(3.15) == 3.5
    assert ceil_to_half(3.0) == 3.0
    assert ceil_to_half(2.01) == 2.5
    assert ceil_to_half(0) == 0.0


def test_adult_equivalent_example():
    bands = {"1-3": 0, "4-6": 1, "7-9": 1, "10-12": 0}
    assert abs(adult_equivalent_exact(2, bands) - 3.15) < 1e-9
    assert adult_equivalent_servings(2, bands) == 3.5


def test_age_bands_match():
    bands = {"1-3": 0, "4-6": 1, "7-9": 1, "10-12": 0}
    assert age_bands_match_children(bands, 2)
    assert not age_bands_match_children(bands, 1)
    assert age_bands_match_children({}, 0)

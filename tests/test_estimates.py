"""Tests for offline price estimates."""

from woolworths_adapter.estimates import estimate_price


def test_estimate_known_ingredient():
    assert estimate_price("milk") == 4.50


def test_estimate_partial_match():
    assert estimate_price("free range chicken breast") == 12.00


def test_estimate_unknown_defaults():
    assert estimate_price("dragon fruit") == 5.00

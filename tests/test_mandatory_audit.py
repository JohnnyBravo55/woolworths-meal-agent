"""Mandatory-item coverage checks for meal-eval / web-smoke audits."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_meal_eval():
    path = Path(__file__).resolve().parents[1] / "scripts" / "meal_eval_run.py"
    spec = importlib.util.spec_from_file_location("meal_eval_run", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_milk_not_satisfied_by_coconut_milk():
    meal_eval = _load_meal_eval()
    items = [
        {
            "ingredient": "coconut milk",
            "product_name": "Coconut Milk (estimated)",
            "is_mandatory": False,
        }
    ]
    assert meal_eval._mandatory_item_covered("milk", items) is False


def test_milk_satisfied_by_plain_milk_line():
    meal_eval = _load_meal_eval()
    items = [
        {
            "ingredient": "milk",
            "product_name": "Standard Milk 2L (estimated)",
            "is_mandatory": True,
        }
    ]
    assert meal_eval._mandatory_item_covered("milk", items) is True


def test_milk_satisfied_by_trim_milk_product():
    meal_eval = _load_meal_eval()
    items = [
        {
            "ingredient": "milk",
            "product_name": "Anchor Trim Milk 2L",
            "is_mandatory": True,
        }
    ]
    assert meal_eval._mandatory_item_covered("milk", items) is True

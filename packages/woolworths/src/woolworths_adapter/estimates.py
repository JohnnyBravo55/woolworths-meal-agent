"""Offline price estimates for demo mode when Woolworths session unavailable."""

from __future__ import annotations

# Rough NZD estimates for common grocery items (demo / offline only)
_ESTIMATES: dict[str, float] = {
    "milk": 4.50,
    "bread": 3.50,
    "chicken": 12.00,
    "chicken breast": 12.00,
    "beef mince": 10.00,
    "rice": 3.00,
    "jasmine rice": 4.00,
    "pasta": 2.50,
    "penne pasta": 2.50,
    "pasta sauce": 4.00,
    "cheese": 6.00,
    "mozzarella": 5.00,
    "eggs": 8.00,
    "onion": 1.50,
    "potatoes": 4.00,
    "broccoli": 3.50,
    "salmon": 18.00,
    "salmon fillets": 18.00,
    "soy sauce": 3.00,
    "honey": 8.00,
    "stir fry vegetables": 4.50,
    "taco shells": 4.00,
    "salsa": 4.00,
    "lettuce": 3.00,
    "olive oil": 8.00,
    "lemon": 1.00,
    "zucchini": 2.50,
    "mushrooms": 4.00,
    "pork sausages": 7.00,
    "peas": 3.00,
    "gravy mix": 2.00,
    "butter": 6.00,
    "tortilla wraps": 5.00,
    "mayonnaise": 4.00,
    "mixed salad leaves": 4.00,
    "tinned tuna": 3.50,
    "cucumber": 2.00,
    "cherry tomatoes": 4.00,
    "crispbread": 4.00,
    "greek yoghurt": 6.00,
    "bananas": 3.50,
    "berries": 6.00,
}

DEFAULT_ESTIMATE = 5.00


def estimate_price(ingredient_name: str) -> float:
    key = ingredient_name.lower().strip()
    if key in _ESTIMATES:
        return _ESTIMATES[key]
    for name, price in _ESTIMATES.items():
        if name in key or key in name:
            return price
    return DEFAULT_ESTIMATE

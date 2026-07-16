"""Pytest configuration."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATHS = [
    ROOT / "packages" / "shared" / "src",
    ROOT / "packages" / "meal_planner" / "src",
    ROOT / "packages" / "woolworths" / "src",
    ROOT / "packages" / "agent" / "src",
    ROOT / "apps" / "cli" / "src",
]
for path in PATHS:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

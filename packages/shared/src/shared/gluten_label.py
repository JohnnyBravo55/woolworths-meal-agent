"""Assess Woolworths product labels for gluten (ingredients + allergen statements)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class GlutenLabelStatus(str, Enum):
    SAFE = "safe"
    TRACES = "traces"
    CONTAINS = "contains"
    UNKNOWN = "unknown"


@dataclass
class ProductLabelInfo:
    """Parsed label fields from a Woolworths product detail response."""

    ingredients: list[str] = field(default_factory=list)
    allergens: list[str] = field(default_factory=list)
    allergen_maybe_present: str | None = None
    claims: list[str] = field(default_factory=list)


@dataclass
class GlutenLabelAssessment:
    status: GlutenLabelStatus
    reasons: list[str] = field(default_factory=list)

    @property
    def user_warning(self) -> str | None:
        if self.status == GlutenLabelStatus.TRACES:
            return (
                "May contain traces of gluten — check label if you are coeliac "
                "or highly sensitive."
            )
        if self.status == GlutenLabelStatus.UNKNOWN:
            return "Could not verify ingredients — check the packaging before buying."
        return None


_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Direct gluten sources in ingredient lists (after GF phrases removed)
_GLUTEN_INGREDIENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bgluten\b", re.I),
    re.compile(r"\bwheat\b", re.I),
    re.compile(r"wheat\s+flour", re.I),
    re.compile(r"wheat\s+starch", re.I),
    re.compile(r"wheat\s+gluten", re.I),
    re.compile(r"\bbarley\b", re.I),
    re.compile(r"barley\s+malt", re.I),
    re.compile(r"malt\s+extract", re.I),
    re.compile(r"\bmalt\b(?!odextrin)", re.I),
    re.compile(r"\brye\b", re.I),
    re.compile(r"\btriticale\b", re.I),
    re.compile(r"\bspelt\b", re.I),
    re.compile(r"\bsemolina\b", re.I),
    re.compile(r"\bdurum\b", re.I),
    re.compile(r"gluten[\s-]*containing\s+cereal", re.I),
)

_GLUTEN_ALLERGEN_WORDS = frozenset(
    {"gluten", "wheat", "barley", "rye", "triticale", "spelt", "malt", "oats"}
)

_GLUTEN_FREE_MARKERS = frozenset(
    {
        "gluten free",
        "gluten-free",
        "free from gluten",
        "no gluten",
    }
)

_MAY_CONTAIN_RE = re.compile(
    r"may\s+(?:be\s+present|contain)(?:\s*:)?\s*([^.;]+)",
    re.I,
)
_CONTAINS_RE = re.compile(
    r"contains\s*:?\s*([^.;]+)",
    re.I,
)


def strip_label_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).replace("\xa0", " ").strip()


def _is_gluten_free_claim(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in _GLUTEN_FREE_MARKERS)


def _remove_gluten_free_phrases(text: str) -> str:
    return re.sub(r"gluten\s*-?\s*free", " ", text, flags=re.I)


def _ingredients_contain_gluten(ingredients: list[str]) -> list[str]:
    hits: list[str] = []
    for raw in ingredients:
        text = strip_label_html(raw)
        if not text:
            continue
        cleaned = _remove_gluten_free_phrases(text)
        for pattern in _GLUTEN_INGREDIENT_PATTERNS:
            if pattern.search(cleaned):
                hits.append(f"Ingredients list: {text[:120]}")
                break
    return hits


def _split_allergen_tokens(chunk: str) -> list[str]:
    return [t.strip().lower() for t in re.split(r"[,;/]", chunk) if t.strip()]


def _chunk_has_gluten(chunk: str) -> bool:
    tokens = _split_allergen_tokens(chunk)
    for token in tokens:
        if token in _GLUTEN_ALLERGEN_WORDS:
            return True
        if any(word in token for word in ("gluten", "wheat", "barley", "rye")):
            if "free" not in token:
                return True
    return False


def _parse_allergen_statements(allergens: list[str], maybe_present: str | None) -> tuple[list[str], list[str]]:
    contains: list[str] = []
    traces: list[str] = []

    for statement in allergens:
        text = strip_label_html(statement)
        if not text:
            continue

        for match in _MAY_CONTAIN_RE.finditer(text):
            part = match.group(1)
            if _chunk_has_gluten(part):
                traces.append(f"Allergen statement: {text}")

        remainder = _MAY_CONTAIN_RE.sub("", text)
        for match in _CONTAINS_RE.finditer(remainder):
            part = match.group(1)
            if _chunk_has_gluten(part):
                contains.append(f"Allergen statement: {text}")

        if _CONTAINS_RE.search(text) or _MAY_CONTAIN_RE.search(text):
            continue

        if _chunk_has_gluten(text):
            contains.append(f"Allergen statement: {text}")

    if maybe_present and _chunk_has_gluten(maybe_present):
        traces.append(f"May be present: {maybe_present}")

    return contains, traces


def assess_gluten_label(label: ProductLabelInfo) -> GlutenLabelAssessment:
    """Classify a product label for gluten-allergic shoppers."""
    combined = " ".join(
        [
            " ".join(label.ingredients),
            " ".join(label.allergens),
            label.allergen_maybe_present or "",
            " ".join(label.claims),
        ]
    )
    if _is_gluten_free_claim(combined):
        ingredient_hits = _ingredients_contain_gluten(label.ingredients)
        contains, traces = _parse_allergen_statements(
            label.allergens, label.allergen_maybe_present
        )
        if contains or ingredient_hits:
            reasons = contains + ingredient_hits
            return GlutenLabelAssessment(GlutenLabelStatus.CONTAINS, reasons)
        if traces:
            return GlutenLabelAssessment(GlutenLabelStatus.TRACES, traces)
        return GlutenLabelAssessment(GlutenLabelStatus.SAFE, ["Labelled gluten free"])

    ingredient_hits = _ingredients_contain_gluten(label.ingredients)
    contains, traces = _parse_allergen_statements(
        label.allergens, label.allergen_maybe_present
    )

    if contains or ingredient_hits:
        reasons = contains + ingredient_hits
        return GlutenLabelAssessment(GlutenLabelStatus.CONTAINS, reasons)

    if traces:
        return GlutenLabelAssessment(GlutenLabelStatus.TRACES, traces)

    if not label.ingredients and not label.allergens and not label.allergen_maybe_present:
        return GlutenLabelAssessment(GlutenLabelStatus.UNKNOWN, ["No label data available"])

    return GlutenLabelAssessment(GlutenLabelStatus.SAFE, [])

"""Helpers shared by vendor modules. No HTTP, no I/O."""

from __future__ import annotations

import re as _re

UNIT_TO_GRAMS: dict[str, float] = {
    "ug": 1e-6,
    "µg": 1e-6,
    "mcg": 1e-6,
    "mg": 1e-3,
    "g": 1.0,
    "gr": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
}


def pack_size_to_grams(size: float, unit: str) -> float:
    """Convert a (size, unit) pair to grams. Raises KeyError on unknown unit."""
    return size * UNIT_TO_GRAMS[unit.lower()]


# Strips molecular-weight / molarity tokens like "308.4 g/mol", "5 mg/mL",
# "1 mg/kg" so vendor regex parsers don't mistake them for pack sizes.
# The first \b(g|mg|kg)\b that gets paired with the first $price on a real
# product page is otherwise the molecular weight, producing prices off by
# 3+ orders of magnitude that then get cached for 30 days.
_MW_TOKEN_RE = _re.compile(
    r"\b[\d.]+\s*(?:mg|g|kg|µg|ug|mcg)\s*/\s*(?:mol|l|kg|ml)\b",
    _re.I,
)


def strip_molarity_tokens(text: str) -> str:
    """Remove `<num> <unit>/<denom>` runs (g/mol, mg/mL, mg/kg, etc.) so they
    don't poison subsequent pack-size regex matches."""
    return _MW_TOKEN_RE.sub("", text)

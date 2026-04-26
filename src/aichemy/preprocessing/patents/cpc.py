"""CPC-code classifier for patent licensing.

Pure function operating on a single patent's CPC codes + filing date,
producing booleans that downstream stages consume. Rules are loaded from
a YAML config so they can be tweaked without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl
import yaml

PATENT_TERM_YEARS = 20


@dataclass
class CPCRules:
    process_codes: list[str]
    composition_codes: list[str]
    ambiguous_codes: list[str]


@dataclass
class CPCClassification:
    patent_active: bool
    cpc_process_hit: bool
    cpc_composition_hit: bool
    cpc_ambiguous: bool
    process_covered_cpc: bool
    composition_covered_cpc: bool


CPC_CLASSIFICATION_SCHEMA = {
    "rxn_id": pl.Utf8,
    "patent_number": pl.Utf8,
    "patent_active": pl.Boolean,
    "cpc_process_hit": pl.Boolean,
    "cpc_composition_hit": pl.Boolean,
    "cpc_ambiguous": pl.Boolean,
    "process_covered_cpc": pl.Boolean,
    "composition_covered_cpc": pl.Boolean,
}


def load_cpc_rules(path: Path) -> CPCRules:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return CPCRules(
        process_codes=list(raw.get("process_codes") or []),
        composition_codes=list(raw.get("composition_codes") or []),
        ambiguous_codes=list(raw.get("ambiguous_codes") or []),
    )


def classify_patent(
    *,
    cpc_codes: list[str],
    filing_date_str: str | None,
    today: date,
    rules: CPCRules,
) -> CPCClassification:
    """Classify one patent. Inactive patents short-circuit to all-False."""
    patent_active = _is_active(filing_date_str, today)
    if not patent_active:
        return CPCClassification(
            patent_active=False,
            cpc_process_hit=False,
            cpc_composition_hit=False,
            cpc_ambiguous=False,
            process_covered_cpc=False,
            composition_covered_cpc=False,
        )

    process_hit = _any_prefix_match(cpc_codes, rules.process_codes)
    composition_hit = _any_prefix_match(cpc_codes, rules.composition_codes)
    ambiguous_explicit = _any_prefix_match(cpc_codes, rules.ambiguous_codes)
    has_any_chemistry = process_hit or composition_hit or ambiguous_explicit

    ambiguous = ambiguous_explicit or (process_hit and composition_hit) or not has_any_chemistry

    return CPCClassification(
        patent_active=True,
        cpc_process_hit=process_hit,
        cpc_composition_hit=composition_hit,
        cpc_ambiguous=ambiguous,
        process_covered_cpc=process_hit and not ambiguous,
        composition_covered_cpc=composition_hit and not ambiguous,
    )


def _any_prefix_match(codes: list[str], prefixes: list[str]) -> bool:
    return any(c.startswith(p) for c in codes for p in prefixes)


def _is_active(filing_date_str: str | None, today: date) -> bool:
    if not filing_date_str:
        return False
    try:
        filed = date.fromisoformat(filing_date_str)
    except ValueError:
        return False
    expiry = date(filed.year + PATENT_TERM_YEARS, filed.month, filed.day)
    return today < expiry


def classify_dataframe(
    reactions: pl.DataFrame,
    patents: pl.DataFrame,
    *,
    rules: CPCRules,
    today: date,
) -> pl.DataFrame:
    """Produce one row per (rxn_id, patent_number) for USPTO reactions."""
    uspto = reactions.filter(pl.col("source") == "uspto")
    rxn_rows = []
    for rid in uspto["rxn_id"].to_list():
        parts = rid.split(":")
        if len(parts) >= 3 and parts[0] == "USPTO":
            rxn_rows.append({"rxn_id": rid, "patent_number": parts[1]})
    rxn_df = pl.DataFrame(rxn_rows, schema={"rxn_id": pl.Utf8, "patent_number": pl.Utf8})

    joined = rxn_df.join(patents, on="patent_number", how="left")

    out_rows: list[dict] = []
    for r in joined.iter_rows(named=True):
        cpc_codes = list(r.get("cpc_codes") or [])
        c = classify_patent(
            cpc_codes=cpc_codes,
            filing_date_str=r.get("filing_date"),
            today=today,
            rules=rules,
        )
        out_rows.append(
            {
                "rxn_id": r["rxn_id"],
                "patent_number": r["patent_number"],
                "patent_active": c.patent_active,
                "cpc_process_hit": c.cpc_process_hit,
                "cpc_composition_hit": c.cpc_composition_hit,
                "cpc_ambiguous": c.cpc_ambiguous,
                "process_covered_cpc": c.process_covered_cpc,
                "composition_covered_cpc": c.composition_covered_cpc,
            }
        )
    return pl.DataFrame(out_rows, schema=CPC_CLASSIFICATION_SCHEMA)

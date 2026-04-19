"""Molecule deduplication (Stage 05).

Primary identity test: InChIKey equality (groups rows with the same InChIKey).
Secondary consistency check: within each group, all rows should have the same
canonical SMILES; a mismatch logs a warning (indicates a canonicalization bug).

Emits:
- A deduped DataFrame with one row per InChIKey group, union of source_refs.
- A dedup_map dict mapping every pre-dedup `mol_id` to its canonical `mol_id`.

Canonical-ID preference: MetaNetX IDs (starting with `MNX`) beat InChIKey-style
IDs. Within a tie, lexically smallest wins.
"""

from __future__ import annotations

import logging

import polars as pl

log = logging.getLogger(__name__)


def _pick_canonical_mol_id(candidates: list[str]) -> str:
    """Return the preferred mol_id: MetaNetX IDs (MNX prefix) beat others."""
    mnx = sorted(c for c in candidates if c.startswith("MNX"))
    if mnx:
        return mnx[0]
    return sorted(candidates)[0]


def dedup_molecules(df: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, str]]:
    """Deduplicate molecules by InChIKey, picking MNX IDs as canonical when present.

    Returns `(deduped_df, dedup_map)` where ``dedup_map[pre_dedup_mol_id] = canonical_mol_id``.
    """
    dedup_map: dict[str, str] = {}
    canonical_rows: list[dict[str, object]] = []

    for inchi_key_tuple, group_df in df.group_by("inchi_key"):
        inchi_key = inchi_key_tuple[0]  # Polars group_by returns (key,) tuples
        group = group_df.to_dicts()

        # Rows with NULL InChIKey can't be grouped meaningfully — emit each
        # as its own canonical entry (they're presumed distinct).
        if inchi_key is None:
            for row in group:
                dedup_map[row["mol_id"]] = row["mol_id"]
                canonical_rows.append(row)
            continue

        mol_ids = [row["mol_id"] for row in group]
        canonical = _pick_canonical_mol_id(mol_ids)

        for mid in mol_ids:
            dedup_map[mid] = canonical

        smiles_set = {row["canonical_smiles"] for row in group if row["canonical_smiles"]}
        if len(smiles_set) > 1:
            log.warning(
                "Molecules with matching InChIKey %r have divergent canonical SMILES: %s",
                inchi_key,
                sorted(smiles_set),
            )

        # Union all source_refs across the group, skipping None-valued lists.
        all_refs = sorted(
            {ref for row in group for ref in (row["source_refs"] or []) if ref is not None}
        )
        template = next(row for row in group if row["mol_id"] == canonical)
        canonical_rows.append(
            {
                "mol_id": canonical,
                "canonical_smiles": template["canonical_smiles"],
                "inchi_key": template["inchi_key"],
                "carbon_count": template["carbon_count"],
                "price_per_gram": template["price_per_gram"],
                "source_refs": all_refs,
            }
        )

    deduped = pl.DataFrame(
        canonical_rows,
        schema_overrides={
            "carbon_count": pl.Int64,
            "price_per_gram": pl.Float64,
            "source_refs": pl.List(pl.Utf8),
        },
    )
    return deduped, dedup_map

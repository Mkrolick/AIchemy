"""Normalize stage (Stage 04).

Merges MetaNetX and USPTO raw interim parquets into unified molecule and
reaction tables. Applies canonical SMILES + carbon counting to every
unique molecule. Applies a hydrocarbon filter removing reactions whose
participants have too few carbons.

This module is the orchestrator; chemistry primitives live in
`aichemy.preprocessing.chem`.
"""

from __future__ import annotations

import logging

import polars as pl

from aichemy.preprocessing.chem.filters import carbon_count
from aichemy.preprocessing.chem.identifiers import inchi_key
from aichemy.preprocessing.chem.smiles import canonicalize, is_valid

log = logging.getLogger(__name__)


def merge_sources(
    metanetx_mol: pl.DataFrame,
    uspto_mol: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Union molecules from available source tables."""
    if uspto_mol is None or uspto_mol.height == 0:
        return metanetx_mol
    return pl.concat([metanetx_mol, uspto_mol], how="diagonal_relaxed")


def extract_uspto_molecules(uspto_reactions: pl.DataFrame) -> pl.DataFrame:
    """Extract unique molecules from USPTO reactions' SMILES-as-mol_id fields.

    USPTO ingestion stores raw SMILES strings as `mol_id` in reactant/product
    structs. To make them filterable/dedupable, extract every distinct SMILES,
    canonicalize it, compute InChIKey + carbon count, and emit a molecules
    DataFrame keyed by a SMILES-derived `mol_id` (we use the canonical SMILES
    itself, which matches the mol_id already stored in the reaction rows).
    """
    if uspto_reactions.height == 0:
        return _empty_molecules()

    # Collect all SMILES used as mol_ids in USPTO reactions.
    smiles_set: set[str] = set()
    for row in uspto_reactions.iter_rows(named=True):
        for s in row["reactants"] + row["products"]:
            if s.get("mol_id"):
                smiles_set.add(s["mol_id"])

    rows: list[dict] = []
    for smi in smiles_set:
        # Strip atom-map labels ([Br:1] -> Br) for canonicalization, but keep
        # the ORIGINAL SMILES as the mol_id so reaction references still resolve.
        try:
            if not is_valid(smi):
                # Atom-mapped SMILES may still be parseable; skip only on hard fail.
                continue
            canon = canonicalize(smi)
            ikey = inchi_key(smi)
            c = carbon_count(smi)
        except Exception:
            log.debug("Skipping unparseable USPTO SMILES: %s", smi[:60])
            continue
        rows.append(
            {
                "mol_id": smi,  # keep original to match reaction refs
                "canonical_smiles": canon,
                "inchi_key": ikey,
                "carbon_count": c,
                "price_per_gram": None,
                "source_refs": [f"USPTO:{smi[:40]}"],
            }
        )

    if not rows:
        return _empty_molecules()

    return pl.DataFrame(
        rows,
        schema_overrides={
            "carbon_count": pl.Int64,
            "price_per_gram": pl.Float64,
            "source_refs": pl.List(pl.Utf8),
        },
    )


def _empty_molecules() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "mol_id": [],
            "canonical_smiles": [],
            "inchi_key": [],
            "carbon_count": [],
            "price_per_gram": [],
            "source_refs": [],
        },
        schema={
            "mol_id": pl.Utf8,
            "canonical_smiles": pl.Utf8,
            "inchi_key": pl.Utf8,
            "carbon_count": pl.Int64,
            "price_per_gram": pl.Float64,
            "source_refs": pl.List(pl.Utf8),
        },
    )


def canonicalize_molecules(df: pl.DataFrame) -> pl.DataFrame:
    """Compute carbon_count (and in future canonical_smiles) for every row."""
    carbon_counts = [carbon_count(smi) for smi in df["canonical_smiles"].to_list()]
    return df.with_columns(pl.Series("carbon_count", carbon_counts, dtype=pl.Int64))


def filter_reactions_by_carbon(
    reactions: pl.DataFrame,
    molecules: pl.DataFrame,
    min_carbon: int = 2,
) -> pl.DataFrame:
    """Drop reactions where any reactant or product has < min_carbon carbons."""
    if reactions.height == 0:
        return reactions

    carbon_by_mol: dict[str, int] = dict(
        zip(
            molecules["mol_id"].to_list(),
            molecules["carbon_count"].to_list(),
            strict=True,
        )
    )

    def _side_has_carbon(side: list) -> bool:
        for stoich in side:
            c = carbon_by_mol.get(stoich["mol_id"], 0)
            if c is not None and c >= min_carbon:
                return True
        return False

    def _passes(row: dict) -> bool:
        # Keep reactions that have at least one "synthesis-relevant" (≥2-C)
        # participant on each side. Drops reactions that are purely small-
        # molecule shuffles (H+, H2O, etc.) while preserving legitimate
        # enzymatic reactions that happen to involve water as co-substrate.
        return _side_has_carbon(row["reactants"]) and _side_has_carbon(row["products"])

    mask = [_passes(row) for row in reactions.iter_rows(named=True)]
    return reactions.filter(pl.Series("_keep", mask, dtype=pl.Boolean))

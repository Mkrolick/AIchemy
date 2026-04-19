"""Normalize stage (Stage 04).

Merges MetaNetX and USPTO raw interim parquets into unified molecule and
reaction tables. Applies canonical SMILES + carbon counting to every
unique molecule. Applies a hydrocarbon filter removing reactions whose
participants have too few carbons.

This module is the orchestrator; chemistry primitives live in
`aichemy.preprocessing.chem`.
"""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.chem.filters import carbon_count


def merge_sources(
    metanetx_mol: pl.DataFrame,
    uspto_mol: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Union molecules from available source tables.

    USPTO ingestion (Stage 03) does not emit a dedicated molecules table
    (reactants/products are bare SMILES embedded in reactions). Once USPTO
    molecule extraction lands, this function will union both. For now,
    pass through MetaNetX molecules.
    """
    if uspto_mol is None or uspto_mol.height == 0:
        return metanetx_mol
    return pl.concat([metanetx_mol, uspto_mol], how="diagonal_relaxed")


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
    carbon_by_mol: dict[str, int] = dict(
        zip(
            molecules["mol_id"].to_list(),
            molecules["carbon_count"].to_list(),
            strict=True,
        )
    )

    def _passes(row: dict[str, object]) -> bool:
        for side_name in ("reactants", "products"):
            for stoich in row[side_name]:
                c = carbon_by_mol.get(stoich["mol_id"], 0)
                if c is None or c < min_carbon:
                    return False
        return True

    mask = [_passes(row) for row in reactions.iter_rows(named=True)]
    return reactions.filter(pl.Series("_keep", mask))

"""Reaction deduplication (Stage 06).

Steps:
1. `rewrite_mol_ids`: apply the `dedup_map` produced by Stage 05 so every
   reactant/product `mol_id` points at its canonical row.
2. Build a canonical reaction string (sorted reactants + sorted products
   with coefficients) and group by it.
3. Within each group, emit one surviving representative row.
4. Assert referential integrity against the deduped molecules table.
"""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl


def rewrite_mol_ids(
    reactions: pl.DataFrame,
    dedup_map: dict[str, str],
) -> pl.DataFrame:
    """Remap every stoichiometry entry's mol_id through dedup_map.

    Unknown ids pass through unchanged so callers can detect dangling
    references via a separate integrity check.
    """
    new_reactants: list[list[dict]] = []
    new_products: list[list[dict]] = []
    for row in reactions.iter_rows(named=True):
        new_reactants.append(
            [
                {
                    "mol_id": dedup_map.get(s["mol_id"], s["mol_id"]),
                    "coefficient": s["coefficient"],
                }
                for s in row["reactants"]
            ]
        )
        new_products.append(
            [
                {
                    "mol_id": dedup_map.get(s["mol_id"], s["mol_id"]),
                    "coefficient": s["coefficient"],
                }
                for s in row["products"]
            ]
        )
    return reactions.with_columns(
        pl.Series("reactants", new_reactants),
        pl.Series("products", new_products),
    )


def canonical_reaction_string(
    reactants: Iterable[dict],
    products: Iterable[dict],
) -> str:
    """Produce a deterministic string representing reactants + products.

    Sorts each side by (mol_id, coefficient) so permutations collapse.
    """

    def _fmt(side: Iterable[dict]) -> str:
        parts = sorted(
            (f"{s['coefficient']:g}*{s['mol_id']}" for s in side),
        )
        return "+".join(parts)

    return f"{_fmt(reactants)}>>{_fmt(products)}"


def _assert_referential_integrity(reactions: pl.DataFrame, molecules: pl.DataFrame) -> None:
    mol_ids = set(molecules["mol_id"].to_list())
    dangling: set[str] = set()
    for row in reactions.iter_rows(named=True):
        for side in (row["reactants"], row["products"]):
            for s in side:
                if s["mol_id"] not in mol_ids:
                    dangling.add(s["mol_id"])
    if dangling:
        raise ValueError(
            f"Reaction references mol_ids absent from molecules table: {sorted(dangling)}"
        )


def dedup_reactions(
    reactions: pl.DataFrame,
    molecules: pl.DataFrame,
    dedup_map: dict[str, str],
) -> pl.DataFrame:
    """Full reaction-dedup pipeline.

    Rewrites mol_ids via dedup_map, drops exact duplicates by canonical
    reaction string, and asserts referential integrity against the
    molecules table.
    """
    rewritten = rewrite_mol_ids(reactions, dedup_map)
    _assert_referential_integrity(rewritten, molecules)

    canonical = [
        canonical_reaction_string(row["reactants"], row["products"])
        for row in rewritten.iter_rows(named=True)
    ]
    return (
        rewritten.with_columns(pl.Series("_canonical", canonical))
        .unique(subset="_canonical", maintain_order=True)
        .drop("_canonical")
    )

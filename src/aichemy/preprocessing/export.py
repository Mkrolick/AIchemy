"""Export stage (Stage 12).

Writes the final unified hypergraph parquets to ``data/processed/`` plus a
``hypergraph_manifest.json`` capturing run metadata. Fails fast if the
deduped/augmented tables have lost referential integrity (any reaction's
mol_id not in the molecules table).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

SPEC_VERSION = "0.0.1"


def assert_referential_integrity(
    reactions: pl.DataFrame,
    molecules: pl.DataFrame,
) -> None:
    """Raise ValueError if any reactant/product mol_id is not in molecules.mol_id.

    Works on the struct-of-list representation of ``reactants`` / ``products``.
    """
    mol_ids = set(molecules["mol_id"].to_list())

    dangling: set[str] = set()
    for row in reactions.iter_rows(named=True):
        for side_name in ("reactants", "products"):
            for stoich in row[side_name]:
                if stoich["mol_id"] not in mol_ids:
                    dangling.add(stoich["mol_id"])

    if dangling:
        raise ValueError(
            f"Referential integrity violation: dangling mol_id(s) {sorted(dangling)} "
            f"present in reactions but absent from molecules"
        )


def write_manifest(
    reactions: pl.DataFrame,
    molecules: pl.DataFrame,
    *,
    metanetx_version: str,
    uspto_slice: str,
    output_path: Path,
    config_hash: str | None = None,
) -> dict[str, Any]:
    """Build the manifest dict, write it to disk as JSON, and return it."""
    balanced_reactions = (
        int(reactions.filter(pl.col("balanced")).height) if "balanced" in reactions.columns else 0
    )
    manifest: dict[str, Any] = {
        "spec_version": SPEC_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "counts": {
            "reactions": int(reactions.height),
            "molecules": int(molecules.height),
            "balanced_reactions": balanced_reactions,
        },
        "sources": {
            "metanetx_version": metanetx_version,
            "uspto_slice": uspto_slice,
        },
    }
    if config_hash is not None:
        manifest["config_hash"] = config_hash

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest

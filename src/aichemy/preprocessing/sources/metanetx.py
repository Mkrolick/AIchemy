"""MetaNetX ingestion (Stage 02).

Parses MetaNetX TSV dumps (`reac_prop.tsv`, `chem_prop.tsv`) into Polars
DataFrames conforming to the internal molecules/reactions schema.

MetaNetX format notes:
- `#` prefixed lines are column-header comments; the first such line is the
  header row (skip the `#`).
- `reac_prop.equation` follows the pattern
  `<coeff> <MNXM_id> + <coeff> <MNXM_id> + ... = <coeff> <MNXM_id> + ...`
  Coefficient is always explicit (even `1`).
- `is_balanced` is a single-letter code: B=balanced, N=not balanced,
  R=redundant. Map B→True, else False.
- `EC` is a semicolon-separated list; take the first for `ec_class`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import polars as pl

_EQUATION_SPLIT = re.compile(r"\s*=\s*")
_COEFF_SMI_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s+(\S+)")
# MetaNetX tags molecule references with a compartment suffix (e.g. `MNXM1@MNXD1`)
# — strip that for molecule-identity matching.
_COMPARTMENT_SUFFIX = re.compile(r"@MNXD\d+$")


def parse_chem_prop(path: Path) -> pl.DataFrame:
    """Parse chem_prop.tsv → DataFrame with one row per molecule."""
    df = pl.read_csv(
        path,
        separator="\t",
        has_header=False,
        comment_prefix="#",
        truncate_ragged_lines=True,
        quote_char=None,
        new_columns=[
            "mnx_id",
            "name",
            "reference",
            "formula",
            "charge",
            "mass",
            "inchi",
            "inchi_key",
            "smiles",
        ],
    )
    return df


def parse_equation(
    equation: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse a MetaNetX equation string into (reactants, products) lists of dicts.

    Each dict has keys ``mol_id`` and ``coefficient``.
    """
    lhs, rhs = _EQUATION_SPLIT.split(equation, maxsplit=1)

    def _parse_side(side: str) -> list[dict[str, Any]]:
        tokens = _COEFF_SMI_PATTERN.findall(side)
        return [
            {
                "mol_id": _COMPARTMENT_SUFFIX.sub("", mol_id),
                "coefficient": float(coeff),
            }
            for coeff, mol_id in tokens
        ]

    return _parse_side(lhs), _parse_side(rhs)


def parse_reac_prop(path: Path) -> pl.DataFrame:
    """Parse reac_prop.tsv → DataFrame with one row per reaction."""
    df = pl.read_csv(
        path,
        separator="\t",
        has_header=False,
        comment_prefix="#",
        truncate_ragged_lines=True,
        quote_char=None,
        new_columns=[
            "mnx_rxn_id",
            "equation",
            "reference",
            "ec",
            "is_balanced",
            "is_transport",
        ],
    )
    parsed_eqs = [parse_equation(eq) for eq in df["equation"].to_list()]
    reactants = [r for r, _ in parsed_eqs]
    products = [p for _, p in parsed_eqs]

    is_balanced = [v == "B" for v in df["is_balanced"].to_list()]
    ec_firsts = [ec.split(";", 1)[0] if ec else None for ec in df["ec"].to_list()]

    return df.with_columns(
        pl.Series("reactants", reactants),
        pl.Series("products", products),
        pl.Series("balanced_mnx", is_balanced),
        pl.Series("ec_class", ec_firsts),
    )


def ingest_metanetx(fixture_dir: Path) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Ingest a MetaNetX TSV snapshot and return (molecules, reactions)."""
    chem_df = parse_chem_prop(fixture_dir / "chem_prop.tsv")
    reac_df = parse_reac_prop(fixture_dir / "reac_prop.tsv")

    molecules = chem_df.select(
        pl.col("mnx_id").alias("mol_id"),
        pl.col("smiles").alias("canonical_smiles"),
        pl.col("inchi_key"),
        pl.lit(None, dtype=pl.Int64).alias("carbon_count"),
        pl.lit(None, dtype=pl.Float64).alias("price_per_gram"),
        pl.concat_list(
            pl.lit("MetaNetX:").cast(pl.Utf8) + pl.col("mnx_id"),
        ).alias("source_refs"),
    )

    reactions = reac_df.select(
        pl.col("mnx_rxn_id").alias("rxn_id"),
        pl.col("equation").alias("reaction_smiles"),
        pl.col("reactants"),
        pl.col("products"),
        pl.lit("enzymatic").alias("type"),
        pl.lit(None, dtype=pl.Float64).alias("yield_rate"),
        pl.lit(None, dtype=pl.Float64).alias("delta_g"),
        pl.col("balanced_mnx").alias("balanced"),
        pl.lit("metanetx").alias("source"),
        pl.col("ec_class"),
        # MetaNetX's `reac_prop.tsv` does not carry an explicit direction flag
        # (unlike mnet-spec). Per proposal: assume forward for MetaNetX rows
        # and use eQuilibrator ΔG'° later to flag thermodynamically infeasible.
        pl.lit("forward").alias("direction"),
    )

    return molecules, reactions

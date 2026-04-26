from __future__ import annotations

import os
from pathlib import Path

import patito as pt
import polars as pl

from aichemy.config import PreprocessingConfig


class Stoichiometry(pt.Model):
    mol_id: str
    coefficient: float


class Molecule(pt.Model):
    mol_id: str
    canonical_smiles: str
    inchi_key: str
    carbon_count: int
    price_per_gram: float | None = None
    source_refs: list[str]


class Reaction(pt.Model):
    rxn_id: str
    reaction_smiles: str
    reactants: list[Stoichiometry]
    products: list[Stoichiometry]
    type: str  # "enzymatic" | "chemical"
    yield_rate: float
    delta_g: float | None = None
    balanced: bool
    source: str  # "metanetx" | "uspto"


def resolve_data_dir(config: PreprocessingConfig) -> Path:
    """Return the data directory, honoring AICHEMY_DATA_DIR env override."""
    env = os.environ.get("AICHEMY_DATA_DIR")
    if env:
        return Path(env)
    return config.paths.data_dir


def raw_path(config: PreprocessingConfig, *parts: str) -> Path:
    return resolve_data_dir(config).joinpath("raw", *parts)


def interim_path(config: PreprocessingConfig, *parts: str) -> Path:
    return resolve_data_dir(config).joinpath("interim", *parts)


def processed_path(config: PreprocessingConfig, *parts: str) -> Path:
    return resolve_data_dir(config).joinpath("processed", *parts)


MOLECULE_SCHEMA = {
    "mol_id": pl.Utf8,
    "canonical_smiles": pl.Utf8,
    "inchi_key": pl.Utf8,
    "carbon_count": pl.Int64,
    "price_per_gram": pl.Float64,
    "source_refs": pl.List(pl.Utf8),
    # Set True by normalize when a wildcard SMILES was rewritten to a concrete
    # exemplar via the class-metabolite resolver. Downstream stages may ignore.
    "is_class_resolved": pl.Boolean,
}

REACTION_SCHEMA = {
    "rxn_id": pl.Utf8,
    "reaction_smiles": pl.Utf8,
    "reactants": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
    "products": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
    "type": pl.Utf8,
    "yield_rate": pl.Float64,
    "delta_g": pl.Float64,
    "balanced": pl.Boolean,
    "source": pl.Utf8,
}


def write_molecules(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)


def write_reactions(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)


def read_molecules(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)


def read_reactions(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)


def write_empty_molecules(path: Path) -> None:
    """Write a schema-valid zero-row molecules parquet."""
    write_molecules(pl.DataFrame(schema=MOLECULE_SCHEMA), path)


def write_empty_reactions(path: Path) -> None:
    """Write a schema-valid zero-row reactions parquet."""
    write_reactions(pl.DataFrame(schema=REACTION_SCHEMA), path)

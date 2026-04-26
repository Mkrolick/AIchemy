from pathlib import Path

import polars as pl
import pytest

from aichemy.config import PreprocessingConfig
from aichemy.preprocessing.io import (
    Molecule,
    Reaction,
    interim_path,
    processed_path,
    raw_path,
    read_molecules,
    read_reactions,
    resolve_data_dir,
    write_empty_molecules,
    write_empty_reactions,
    write_molecules,
)


def test_resolve_data_dir_from_config(tmp_path: Path) -> None:
    cfg = PreprocessingConfig()
    cfg.paths.data_dir = tmp_path / "mydata"
    assert resolve_data_dir(cfg) == tmp_path / "mydata"


def test_resolve_data_dir_env_var_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = PreprocessingConfig()
    cfg.paths.data_dir = Path("/unused")
    monkeypatch.setenv("AICHEMY_DATA_DIR", str(tmp_path / "envdata"))
    assert resolve_data_dir(cfg) == tmp_path / "envdata"


def test_raw_interim_processed_paths(tmp_path: Path) -> None:
    cfg = PreprocessingConfig()
    cfg.paths.data_dir = tmp_path
    assert raw_path(cfg, "metanetx", "reac_prop.tsv") == (
        tmp_path / "raw" / "metanetx" / "reac_prop.tsv"
    )
    assert interim_path(cfg, "normalized", "reactions.parquet") == (
        tmp_path / "interim" / "normalized" / "reactions.parquet"
    )
    assert processed_path(cfg, "reactions.parquet") == (
        tmp_path / "processed" / "reactions.parquet"
    )


def test_molecule_schema_accepts_valid_row() -> None:
    df = pl.DataFrame(
        {
            "mol_id": ["MNXM1"],
            "canonical_smiles": ["O"],
            "inchi_key": ["XLYOFNOQVPJJNP-UHFFFAOYSA-N"],
            "carbon_count": [0],
            "price_per_gram": [None],
            "source_refs": [["MetaNetX:MNXM1"]],
        },
        schema_overrides={"price_per_gram": pl.Float64, "source_refs": pl.List(pl.Utf8)},
    )
    Molecule.validate(df)


def test_molecule_schema_rejects_missing_column() -> None:
    import patito.exceptions

    df = pl.DataFrame({"mol_id": ["MNXM1"]})
    with pytest.raises(patito.exceptions.DataFrameValidationError):
        Molecule.validate(df)


def test_reaction_schema_accepts_valid_row() -> None:
    df = pl.DataFrame(
        {
            "rxn_id": ["MNXR1"],
            "reaction_smiles": ["O>>O"],
            "reactants": [[{"mol_id": "MNXM1", "coefficient": 1.0}]],
            "products": [[{"mol_id": "MNXM1", "coefficient": 1.0}]],
            "type": ["enzymatic"],
            "yield_rate": [0.85],
            "delta_g": [None],
            "balanced": [True],
            "source": ["metanetx"],
        },
        schema_overrides={"delta_g": pl.Float64},
    )
    Reaction.validate(df)


def test_molecules_round_trip(tmp_path: Path) -> None:
    df = pl.DataFrame(
        {
            "mol_id": ["MNXM1"],
            "canonical_smiles": ["O"],
            "inchi_key": ["XLYOFNOQVPJJNP-UHFFFAOYSA-N"],
            "carbon_count": [0],
            "price_per_gram": [None],
            "source_refs": [["MetaNetX:MNXM1"]],
        },
        schema_overrides={"price_per_gram": pl.Float64, "source_refs": pl.List(pl.Utf8)},
    )
    path = tmp_path / "mol.parquet"
    write_molecules(df, path)
    assert path.exists()
    loaded = read_molecules(path)
    assert loaded.equals(df)


def test_write_empty_molecules_is_readable(tmp_path: Path) -> None:
    path = tmp_path / "empty_mol.parquet"
    write_empty_molecules(path)
    assert path.exists()
    df = read_molecules(path)
    assert df.height == 0
    assert set(df.columns) == {
        "mol_id",
        "canonical_smiles",
        "inchi_key",
        "carbon_count",
        "price_per_gram",
        "source_refs",
        "is_class_resolved",
    }


def test_write_empty_reactions_is_readable(tmp_path: Path) -> None:
    path = tmp_path / "empty_rxn.parquet"
    write_empty_reactions(path)
    df = read_reactions(path)
    assert df.height == 0
    assert set(df.columns) == {
        "rxn_id",
        "reaction_smiles",
        "reactants",
        "products",
        "type",
        "yield_rate",
        "delta_g",
        "balanced",
        "rdkit_balanced",
        "source",
    }

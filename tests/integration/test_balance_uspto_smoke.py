"""Smoke test: balance_uspto chunks 100 USPTO rows through SYN-RBL.

Exercises the chunking loop in cli.py with --chunk-size 25 --workers 1:
  - 100 rows / 25 per chunk → 4 SYN-RBL batches
  - Verifies all 4 chunk log lines are emitted
  - Verifies output parquet has 100 rows and is well-formed

Skipped automatically when synrbl is not installed (optional dep).
Marked slow — excluded from the default pytest run; enable with -m slow.
"""

from __future__ import annotations

import pytest

pytest.importorskip("synrbl", reason="synrbl not installed; `uv sync --extra balance` to enable")

from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from aichemy.cli import app
from aichemy.preprocessing.io import REACTION_SCHEMA, write_reactions

runner = CliRunner()

# Ten representative USPTO-format reaction SMILES (3-part reactants>agents>products).
# Chosen to be chemically plausible and small so SYN-RBL processes them quickly.
_SAMPLE_SMILES = [
    "CC(=O)O.Oc1ccccc1>>CC(=O)Oc1ccccc1.O",
    "CCO.CC(=O)Cl>>CCOC(C)=O.[H]Cl",
    "c1ccccc1.Br>>Brc1ccccc1.[H]Br",
    "CC(=O)Cl.O>>CC(=O)O.[H]Cl",
    "CCO.[Na]>>CCO[Na].[H][H]",
    "CC(=O)O.[Na]O>>CC(=O)[O-].[Na+].O",
    "BrCCBr.[Na]I>>ICCBr.[Na]Br",
    "c1ccccc1N.CC(=O)Cl>>CC(=O)Nc1ccccc1.[H]Cl",
    "CCCO.c1ccccc1C(=O)O>>CCCOc(=O)c1ccccc1.O",
    "CC(C)=O.[H][H]>>CC(C)O",
]


def _make_uspto_reactions(n: int) -> pl.DataFrame:
    """Return a schema-valid reactions DataFrame with n USPTO rows."""
    smiles = [_SAMPLE_SMILES[i % len(_SAMPLE_SMILES)] for i in range(n)]
    return pl.DataFrame(
        {
            "rxn_id": [f"smoke_{i:04d}" for i in range(n)],
            "reaction_smiles": smiles,
            "reactants": [[] for _ in range(n)],
            "products": [[] for _ in range(n)],
            "type": ["chemical"] * n,
            "yield_rate": [0.8] * n,
            "delta_g": [None] * n,
            "balanced": [False] * n,
            "source": ["uspto"] * n,
        },
        schema=REACTION_SCHEMA,
    )


@pytest.mark.slow
def test_balance_uspto_smoke_100_rows_4_chunks(tmp_path: Path) -> None:
    """balance_uspto processes 100 rows in exactly 4 chunks of 25."""
    config_path = tmp_path / "cfg.yaml"
    config_path.write_text(f"paths:\n  data_dir: {tmp_path}\n")

    # Stage input: 100 USPTO reactions
    input_dir = tmp_path / "interim" / "deduped"
    input_dir.mkdir(parents=True)
    write_reactions(_make_uspto_reactions(100), input_dir / "reactions.parquet")

    result = runner.invoke(
        app,
        [
            "balance",
            "uspto",
            "--config",
            str(config_path),
            "--chunk-size",
            "25",
            "--workers",
            "1",
        ],
    )

    assert result.exit_code == 0, f"CLI failed:\n{result.stdout}"

    # All four chunk progress lines must appear
    for chunk_n in range(1, 5):
        assert f"chunk {chunk_n}/4" in result.stdout, (
            f"Expected 'chunk {chunk_n}/4' in output; got:\n{result.stdout}"
        )

    # Output parquet must exist with all 100 rows intact
    output_path = tmp_path / "interim" / "balanced" / "reactions.parquet"
    assert output_path.exists(), "balanced/reactions.parquet not created"
    out_df = pl.read_parquet(output_path)
    assert out_df.height == 100, f"Expected 100 rows, got {out_df.height}"

    # 'balanced' column must be present and boolean
    assert "balanced" in out_df.columns
    assert out_df["balanced"].dtype == pl.Boolean

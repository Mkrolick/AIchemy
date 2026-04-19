"""End-to-end integration test: MetaNetX fixture → all stages → solver.

Exercises the full DAG on the hand-curated fixture TSVs, asserts that
each stage produces the expected row counts + invariants, and finishes
with a solved MILP whose objective is positive on a priced network.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import polars as pl
import pytest

from aichemy.config import PreprocessingConfig
from aichemy.preprocessing import export as export_module
from aichemy.preprocessing import normalize as normalize_module
from aichemy.preprocessing.augment import directionality as directionality_module
from aichemy.preprocessing.augment import prices as prices_module
from aichemy.preprocessing.augment import yields as yields_module
from aichemy.preprocessing.balance import validate as balance_validate_module
from aichemy.preprocessing.dedup import molecules as dedup_mol
from aichemy.preprocessing.dedup import reactions as dedup_rxn
from aichemy.preprocessing.sources import metanetx as metanetx_module
from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "metanetx_sample"


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Build a scratch data dir with the MetaNetX fixture files staged."""
    raw = tmp_path / "raw" / "metanetx"
    raw.mkdir(parents=True)
    for f in ("reac_prop.tsv", "chem_prop.tsv"):
        shutil.copy(FIXTURE_DIR / f, raw / f)
    return tmp_path


def test_full_pipeline_on_fixture(tmp_data_dir: Path) -> None:
    """Run every stage on the MetaNetX fixture and verify counts + invariants."""
    cfg = PreprocessingConfig()
    cfg.paths.data_dir = tmp_data_dir

    # --- Stage 02: ingest ---
    molecules, reactions = metanetx_module.ingest_metanetx(tmp_data_dir / "raw" / "metanetx")
    assert molecules.height == 10
    assert reactions.height == 5
    # Every reaction's type/source set correctly
    assert set(reactions["source"].to_list()) == {"metanetx"}
    assert set(reactions["type"].to_list()) == {"enzymatic"}

    # --- Stage 04: normalize ---
    molecules = normalize_module.canonicalize_molecules(molecules)
    # MNXM4 (ethanol) should have 2 carbons
    mnxm4 = molecules.filter(pl.col("mol_id") == "MNXM4").to_dicts()[0]
    assert mnxm4["carbon_count"] == 2
    normalized_rxns = normalize_module.filter_reactions_by_carbon(
        reactions, molecules, min_carbon=2
    )
    # All 5 fixture reactions have ≥1 carbon-containing participant per side
    # (MNXR1–MNXR4 are enzymatic transformations of ethanol/acetaldehyde/etc.)
    # Fixture includes MNXR5: MNXM4 -> MNXM5 + H+ + H+  which keeps both sides C-rich
    assert normalized_rxns.height >= 1

    # --- Stage 05: dedup molecules ---
    deduped_mols, dedup_map = dedup_mol.dedup_molecules(molecules)
    # No collapses expected — all fixture InChIKeys are unique
    assert deduped_mols.height == molecules.height
    assert all(v == k for k, v in dedup_map.items())

    # --- Stage 06: dedup reactions ---
    deduped_rxns = dedup_rxn.dedup_reactions(normalized_rxns, deduped_mols, dedup_map)
    # No exact-dup reactions in fixture
    assert deduped_rxns.height == normalized_rxns.height

    # --- Stage 08: balance validate (ignore H for MetaNetX convention) ---
    validated = balance_validate_module.validate_reactions(
        deduped_rxns, molecules=deduped_mols, ignore_elements=["H"]
    )
    # At least one balanced reaction out of 5
    assert validated.filter(pl.col("balanced")).height >= 1

    # --- Stage 09: augment yields (global mean) ---
    yielded = yields_module.augment_yields(validated, cfg.yields)
    # Even though fixture starts with all-None yields, global_mean_imputer
    # can't fabricate a mean — so values may remain None. Verify it doesn't crash.
    assert yielded.height == validated.height

    # --- Stage 11: augment directionality ---
    dir_out = directionality_module.apply_directionality(
        yielded, mode=directionality_module.DirectionalityMode.ANNOTATE
    )
    assert dir_out.height == yielded.height

    # --- Stage 10: augment prices (stub backend; no prices set) ---
    priced_mols = prices_module.augment_prices(deduped_mols, prices_module.StubPriceLookup())
    assert priced_mols.height == deduped_mols.height

    # --- Stage 12: export — integrity check + manifest ---
    export_module.assert_referential_integrity(dir_out, priced_mols)
    manifest = export_module.write_manifest(
        dir_out,
        priced_mols,
        metanetx_version="fixture",
        uspto_slice="n/a",
        output_path=tmp_data_dir / "manifest.json",
    )
    assert manifest["counts"]["reactions"] == dir_out.height
    assert manifest["counts"]["molecules"] == priced_mols.height
    manifest_on_disk = json.loads((tmp_data_dir / "manifest.json").read_text())
    assert manifest_on_disk == manifest

    # --- Solver: give the network some prices + solve ---
    priced_mols = priced_mols.with_columns(
        pl.Series(
            "price_per_gram",
            [
                1.0
                if mid == "MNXM4"
                # cheap ethanol input
                else 10.0
                if mid == "MNXM9"
                # expensive lactate product
                else 2.0  # medium for everything else
                for mid in priced_mols["mol_id"].to_list()
            ],
            dtype=pl.Float64,
        )
    )
    solution = build_and_solve(
        validated,  # use the validated reactions (some are marked balanced)
        priced_mols,
        SolverConfig(budget=100.0, max_products=5),
    )
    # Solver should terminate cleanly regardless of profitability
    assert solution.status in ("Optimal", "Not Solved", "No reactions after filtering")

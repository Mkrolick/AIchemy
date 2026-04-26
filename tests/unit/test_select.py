"""Tests for the curated-subset selection stage (Stage 14)."""

from __future__ import annotations

import polars as pl

from aichemy.preprocessing.select import (
    compute_idf,
    compute_mol_doc_freq,
    select_reactions,
)

REACTION_SUBSET_SCHEMA = {
    "rxn_id": pl.Utf8,
    "reactants": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
    "products": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
    "rdkit_balanced": pl.Boolean,
}


def _stoich(mol_id: str, coeff: float = 1.0) -> dict:
    return {"mol_id": mol_id, "coefficient": float(coeff)}


def _row(rxn_id: str, reactants: list[str], products: list[str], *, rdkit_balanced: bool) -> dict:
    return {
        "rxn_id": rxn_id,
        "reactants": [_stoich(m) for m in reactants],
        "products": [_stoich(m) for m in products],
        "rdkit_balanced": rdkit_balanced,
    }


def _make_df(rows: list[dict], extra_schema: dict | None = None) -> pl.DataFrame:
    schema = dict(REACTION_SUBSET_SCHEMA)
    if extra_schema:
        schema.update(extra_schema)
    return pl.DataFrame(rows, schema=schema)


def test_empty_input_returns_empty() -> None:
    df = _make_df([])
    out = select_reactions(df, target_total=10, seed=42, mandatory_column="rdkit_balanced")
    assert out.height == 0


def test_total_below_target_returns_all() -> None:
    rows = [
        _row(f"r{i:03d}", ["A"], ["B"], rdkit_balanced=(i % 2 == 0)) for i in range(50)
    ]
    df = _make_df(rows)
    out = select_reactions(df, target_total=100, seed=42, mandatory_column="rdkit_balanced")
    assert out.height == 50
    assert set(out["rxn_id"].to_list()) == {f"r{i:03d}" for i in range(50)}


def test_must_keep_at_or_above_target_truncates() -> None:
    rows = [_row(f"r{i:03d}", ["A"], ["B"], rdkit_balanced=True) for i in range(200)]
    df = _make_df(rows)
    out = select_reactions(df, target_total=100, seed=42, mandatory_column="rdkit_balanced")
    assert out.height == 100
    # Sorted by rxn_id → first 100 lex-sorted ids.
    assert out["rxn_id"].to_list() == [f"r{i:03d}" for i in range(100)]


def test_must_keep_all_present() -> None:
    must_keep_ids = {"k0", "k1", "k2", "k3", "k4"}
    rows = [_row(rid, ["A"], ["B"], rdkit_balanced=True) for rid in must_keep_ids]
    rows += [
        _row(f"c{i}", [f"X{i}"], [f"Y{i}"], rdkit_balanced=False) for i in range(20)
    ]
    df = _make_df(rows)
    out = select_reactions(df, target_total=10, seed=42, mandatory_column="rdkit_balanced")
    assert out.height == 10
    assert must_keep_ids.issubset(set(out["rxn_id"].to_list()))


def test_overlap_preferred_over_disjoint() -> None:
    rows = [
        _row("anchor", ["A", "B"], [], rdkit_balanced=True),
        # Two candidates that share at least one mol_id with the anchor.
        _row("overlap1", ["A"], ["P1"], rdkit_balanced=False),
        _row("overlap2", ["B"], ["P2"], rdkit_balanced=False),
        # Three disjoint candidates.
        _row("disjoint1", ["X1"], ["Y1"], rdkit_balanced=False),
        _row("disjoint2", ["X2"], ["Y2"], rdkit_balanced=False),
        _row("disjoint3", ["X3"], ["Y3"], rdkit_balanced=False),
    ]
    df = _make_df(rows)
    out = select_reactions(df, target_total=3, seed=42, mandatory_column="rdkit_balanced")
    assert set(out["rxn_id"].to_list()) == {"anchor", "overlap1", "overlap2"}


def test_tfidf_downweights_common_mol() -> None:
    """A candidate sharing a RARE mol with the anchor beats one sharing a COMMON mol."""
    rows = [
        # Anchor references both A (common) and B (rare).
        _row("anchor", ["A", "B"], [], rdkit_balanced=True),
        # Candidate sharing only A (a common cofactor).
        _row("cand_common", ["A"], ["P_common"], rdkit_balanced=False),
        # Candidate sharing only B (a rare intermediate).
        _row("cand_rare", ["B"], ["P_rare"], rdkit_balanced=False),
    ]
    # Inflate A's doc-frequency with filler reactions so idf(A) << idf(B).
    rows += [
        _row(f"filler{i}", ["A"], [f"Z{i}"], rdkit_balanced=False) for i in range(30)
    ]
    df = _make_df(rows)
    # target_total = must_keep (1) + 1 fill = 2 → best single candidate must win.
    out = select_reactions(df, target_total=2, seed=42, mandatory_column="rdkit_balanced")
    assert out.height == 2
    assert set(out["rxn_id"].to_list()) == {"anchor", "cand_rare"}


def test_seeded_random_fills_score_zero_candidates() -> None:
    """When all fill candidates have score=0, the seeded tiebreak makes the result deterministic."""
    rows = [
        _row("anchor", ["A"], ["B"], rdkit_balanced=True),
    ]
    rows += [
        _row(f"c{i:03d}", [f"X{i}"], [f"Y{i}"], rdkit_balanced=False) for i in range(20)
    ]
    df = _make_df(rows)
    out1 = select_reactions(df, target_total=5, seed=42, mandatory_column="rdkit_balanced")
    out2 = select_reactions(df, target_total=5, seed=42, mandatory_column="rdkit_balanced")
    assert out1.height == 5
    assert out1["rxn_id"].to_list() == out2["rxn_id"].to_list()


def test_mandatory_column_balanced() -> None:
    """Switching mandatory_column to 'balanced' changes which rows are pinned."""
    # Construct rows where rdkit_balanced and balanced disagree.
    rows = [
        {**_row("r0", ["A"], ["B"], rdkit_balanced=True), "balanced": False},
        {**_row("r1", ["A"], ["B"], rdkit_balanced=False), "balanced": True},
        {**_row("r2", ["A"], ["B"], rdkit_balanced=True), "balanced": True},
        {**_row("r3", ["C"], ["D"], rdkit_balanced=False), "balanced": False},
        {**_row("r4", ["E"], ["F"], rdkit_balanced=False), "balanced": False},
    ]
    df = _make_df(rows, extra_schema={"balanced": pl.Boolean})

    # target_total = mandatory count means the function returns just the pinned set
    # (must_keep.height >= target_total branch). This isolates the pinning mechanism
    # from the fill ranking.
    out_rdkit = select_reactions(df, target_total=2, seed=42, mandatory_column="rdkit_balanced")
    out_balanced = select_reactions(df, target_total=2, seed=42, mandatory_column="balanced")

    assert set(out_rdkit["rxn_id"].to_list()) == {"r0", "r2"}
    assert set(out_balanced["rxn_id"].to_list()) == {"r1", "r2"}


def test_compute_mol_doc_freq_dedupes_within_row() -> None:
    rows = [
        _row("r0", ["A", "A"], ["A", "B"], rdkit_balanced=True),  # mol A on both sides
        _row("r1", ["B"], ["C"], rdkit_balanced=True),
    ]
    df = _make_df(rows)
    doc_freq = compute_mol_doc_freq(df)
    assert doc_freq == {"A": 1, "B": 2, "C": 1}


def test_compute_idf_smoothing() -> None:
    # n=10, df=10 → log(11/11) + 1 = 1.0
    idf = compute_idf({"common": 10}, n_docs=10)
    assert abs(idf["common"] - 1.0) < 1e-9
    # Rare mol gets a higher idf.
    idf2 = compute_idf({"rare": 1, "common": 10}, n_docs=10)
    assert idf2["rare"] > idf2["common"]

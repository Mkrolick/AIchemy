"""Curated-subset selection (Stage 14: select_reactions).

Given the post-augmentation reactions table, produce a fixed-size subset that
pins all rows where ``mandatory_column`` is True (typically ``rdkit_balanced``)
and fills the remainder by preferring candidates whose mol_ids overlap with
the pinned set, weighted by smoothed TF-IDF so common cofactors (water, ATP,
NAD+, …) don't dominate the score. Ties are broken by a seeded hash so
reruns are bit-identical.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter

import polars as pl


def compute_mol_doc_freq(df: pl.DataFrame) -> dict[str, int]:
    """Count, for each mol_id, the number of reactions in which it appears.

    A mol_id is counted at most once per reaction (a row that lists the same
    mol on both sides, or twice on one side, contributes 1, not 2).
    """
    doc_freq: Counter[str] = Counter()
    for row in df.iter_rows(named=True):
        mol_ids: set[str] = set()
        for stoich in row["reactants"]:
            mol_ids.add(stoich["mol_id"])
        for stoich in row["products"]:
            mol_ids.add(stoich["mol_id"])
        doc_freq.update(mol_ids)
    return dict(doc_freq)


def compute_idf(doc_freq: dict[str, int], n_docs: int) -> dict[str, float]:
    """Smoothed IDF: ``log((N + 1) / (df + 1)) + 1``.

    The +1s prevent log(0) and ensure idf > 0 for every observed mol.
    """
    return {
        mol_id: math.log((n_docs + 1) / (df_count + 1)) + 1.0
        for mol_id, df_count in doc_freq.items()
    }


def _row_mol_ids(row: dict[str, list[dict[str, str | float]]]) -> set[str]:
    out: set[str] = set()
    for stoich in row["reactants"]:
        out.add(str(stoich["mol_id"]))
    for stoich in row["products"]:
        out.add(str(stoich["mol_id"]))
    return out


def score_candidates(
    candidates: pl.DataFrame,
    anchor_mol_ids: set[str],
    idf: dict[str, float],
) -> pl.Series:
    """Per-row score = sum of idf weights over mol_ids shared with the anchor set."""
    scores: list[float] = []
    for row in candidates.iter_rows(named=True):
        shared = _row_mol_ids(row) & anchor_mol_ids
        scores.append(sum(idf.get(m, 0.0) for m in shared))
    return pl.Series("score", scores, dtype=pl.Float64)


def _tiebreak(rxn_id: str, seed: int) -> int:
    """Deterministic uniform-ish 32-bit int from (rxn_id, seed).

    Uses BLAKE2b instead of Python's built-in hash() because the latter is
    salted per process (PYTHONHASHSEED) and would make reruns non-reproducible.
    """
    digest = hashlib.blake2b(f"{rxn_id}:{seed}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") & 0xFFFFFFFF


def select_reactions(
    df: pl.DataFrame,
    *,
    target_total: int,
    seed: int,
    mandatory_column: str,
) -> pl.DataFrame:
    """Return up to ``target_total`` rows, pinning all ``mandatory_column=True`` rows.

    Edge cases (each short-circuits):
    - empty input → return unchanged
    - ``df.height <= target_total`` → return all rows sorted by rxn_id
    - mandatory rows already exceed target → truncate mandatory deterministically
    """
    if df.height == 0:
        return df

    if df.height <= target_total:
        return df.sort("rxn_id")

    must_keep = df.filter(pl.col(mandatory_column))
    candidates = df.filter(~pl.col(mandatory_column))

    if must_keep.height >= target_total:
        return must_keep.sort("rxn_id").head(target_total)

    fill_count = target_total - must_keep.height

    doc_freq = compute_mol_doc_freq(df)
    idf = compute_idf(doc_freq, df.height)

    anchor_mol_ids: set[str] = set()
    for row in must_keep.iter_rows(named=True):
        anchor_mol_ids |= _row_mol_ids(row)

    score = score_candidates(candidates, anchor_mol_ids, idf)
    tiebreak = pl.Series(
        "_tiebreak",
        [_tiebreak(rxn_id, seed) for rxn_id in candidates["rxn_id"].to_list()],
        dtype=pl.UInt64,
    )

    selected = (
        candidates.with_columns(score, tiebreak)
        .sort(["score", "_tiebreak"], descending=[True, False])
        .head(fill_count)
        .drop(["score", "_tiebreak"])
    )

    return pl.concat([must_keep, selected]).sort("rxn_id")

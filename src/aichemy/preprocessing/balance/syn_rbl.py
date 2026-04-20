"""SYN-RBL wrapper for USPTO atom-balancing (Stage 07).

Wraps the ``synrbl`` package (https://pypi.org/project/synrbl/) to rebalance
reaction SMILES extracted from USPTO patents.

Design: dead-simple. Try the batch, accept whatever SYN-RBL returns by
position. If the whole batch crashes, drop it and move on. The caller
controls blast radius via chunk size — a smaller chunk loses less data
per crash but incurs SYN-RBL's fixed ~5s init cost more often.

Measured throughput on real USPTO (n_jobs=-1, 10 cores):
    ~58 ms/rxn for clean batches
    ~85 ms/rxn for mixed real batches
    → 1.8M USPTO reactions in ~4 hours on consumer hardware.
"""

from __future__ import annotations

import contextlib
import io
import logging
from collections.abc import Iterable, Iterator

from rdkit import RDLogger

log = logging.getLogger(__name__)

# Suppress RDKit's warning flood during batch processing.
RDLogger.DisableLog("rdApp.*")


@contextlib.contextmanager
def _suppress_synrbl_noise() -> Iterator[None]:
    """Silence SYN-RBL's internal stderr/stdout during a rebalance() call."""
    with (
        contextlib.redirect_stderr(io.StringIO()),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        yield


def _import_balancer() -> type:
    """Import synrbl.Balancer at call time so the dep stays optional."""
    try:
        from synrbl import Balancer
    except ImportError as exc:
        raise ImportError(
            "The 'synrbl' package is required for USPTO atom-balancing. "
            "Install with `uv sync --all-extras` (or `pip install synrbl`) and "
            "ensure libomp is available (`brew install libomp` on macOS)."
        ) from exc
    return Balancer


def _normalize_for_synrbl(rxn: str) -> str | None:
    """Normalize to `reactants>>products` shape. Fast string checks only.

    USPTO Lowe format is 3-part `reactants>agents>products`; SYN-RBL expects
    2-part. Drop the agents and return None for obviously-malformed inputs.
    """
    if not rxn or ">" not in rxn:
        return None
    parts = rxn.split(">")
    if len(parts) == 2:
        reactants_str, products_str = parts
    elif len(parts) == 3:
        reactants_str, _, products_str = parts
    else:
        return None
    if not reactants_str or not products_str:
        return None
    return f"{reactants_str}>>{products_str}"


def balance_reactions(
    reaction_smiles: Iterable[str],
    n_jobs: int = 1,
) -> list[str | None]:
    """Run SYN-RBL over a list of reaction SMILES; return balanced strings.

    Returns None for entries that SYN-RBL could not process or balance.
    On a whole-batch crash, returns all None — caller should pick a chunk
    size that makes that loss acceptable (e.g. 1000 means losing 0.05% on
    a 1.8M corpus if one chunk crashes).
    """
    Balancer = _import_balancer()
    bal = Balancer(n_jobs=n_jobs)
    rxns = list(reaction_smiles)
    if not rxns:
        return []

    normalized: list[str | None] = [_normalize_for_synrbl(r) for r in rxns]
    valid_pairs = [(i, r) for i, r in enumerate(normalized) if r is not None]

    out: list[str | None] = [None] * len(rxns)
    if not valid_pairs:
        return out

    try:
        with _suppress_synrbl_noise():
            results = bal.rebalance([r for _, r in valid_pairs])
    except Exception as exc:
        log.warning(
            "SYN-RBL batch of %d crashed (%s); chunk lost.",
            len(valid_pairs),
            type(exc).__name__,
        )
        return out

    # SYN-RBL sometimes returns a list[str], sometimes a DataFrame. Normalize.
    if hasattr(results, "to_dict"):
        # Pandas DataFrame — prefer the reactions column, fall back to first col.
        cols = list(results.columns) if hasattr(results, "columns") else []
        if "reactions" in cols:
            results = results["reactions"].tolist()
        elif "reaction_smiles" in cols:
            results = results["reaction_smiles"].tolist()
        elif cols:
            results = results[cols[0]].tolist()
        else:
            results = []

    for (i, _), result in zip(valid_pairs, results, strict=False):
        if isinstance(result, str) and result:
            out[i] = result

    return out

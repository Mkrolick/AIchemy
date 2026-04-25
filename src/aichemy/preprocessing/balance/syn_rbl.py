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
) -> list[tuple[str | None, float | None]]:
    """Run SYN-RBL over a list of reaction SMILES; return (smiles, confidence).

    Per-input return semantics:
      * ``(None, None)``         — SYN-RBL produced no usable output for this
                                   input (filtered as malformed, dropped by
                                   SYN-RBL, or whole-batch crash).
      * ``(smiles, None)``       — solved by a deterministic path
                                   (``rule-based`` / ``input-balanced``);
                                   SYN-RBL does not report a confidence score
                                   for these — they're rule-driven bookkeeping.
      * ``(smiles, float)``      — solved by ``mcs-based`` imputation; the
                                   float is SYN-RBL's confidence in [0, 1].
                                   Callers should apply their own threshold.

    On a whole-batch crash, returns all ``(None, None)`` — caller should
    pick a chunk size that makes that loss acceptable (e.g. 1000 means
    losing 0.05% on a 1.8M corpus if one chunk crashes).
    """
    Balancer = _import_balancer()
    bal = Balancer(n_jobs=n_jobs)
    rxns = list(reaction_smiles)
    if not rxns:
        return []

    normalized: list[str | None] = [_normalize_for_synrbl(r) for r in rxns]
    valid_pairs = [(i, r) for i, r in enumerate(normalized) if r is not None]

    out: list[tuple[str | None, float | None]] = [(None, None)] * len(rxns)
    if not valid_pairs:
        return out

    try:
        with _suppress_synrbl_noise():
            results = bal.rebalance([r for _, r in valid_pairs], output_dict=True)
    except Exception as exc:
        log.warning(
            "SYN-RBL batch of %d crashed (%s); chunk lost.",
            len(valid_pairs),
            type(exc).__name__,
        )
        return out

    for (i, _), result in zip(valid_pairs, results, strict=False):
        if not isinstance(result, dict) or not result.get("solved"):
            continue
        reaction = result.get("reaction")
        if not isinstance(reaction, str) or not reaction:
            continue
        confidence = result.get("confidence")
        out[i] = (reaction, float(confidence) if confidence is not None else None)

    return out

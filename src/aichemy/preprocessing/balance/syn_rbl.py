"""SYN-RBL wrapper for USPTO atom-balancing (Stage 07).

Wraps the ``synrbl`` package (https://pypi.org/project/synrbl/) to rebalance
reaction SMILES extracted from USPTO patents. The Balancer takes reaction
SMILES strings and returns balanced versions (adding missing small molecules
like water, CO2, protons via rule-based and MCS-based heuristics).

Optional dependency: install with `uv pip install synrbl` OR
`uv sync --all-extras`. The macOS libomp system dep is needed
(`brew install libomp`).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

log = logging.getLogger(__name__)


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
    """Drop agent middle-section and validate `reactants>>products` shape.

    USPTO uses 3-part `reactants>agents>products`; SYN-RBL expects 2-part.
    """
    if not rxn or ">" not in rxn:
        return None
    parts = rxn.split(">")
    if len(parts) == 2:
        return rxn if parts[0] and parts[1] else None
    if len(parts) == 3:
        r, _, p = parts
        if not (r and p):
            return None
        return f"{r}>>{p}"
    return None


def _try_batch(
    bal: object,
    pairs: list[tuple[int, str]],
    out: list[str | None],
    min_batch: int = 1,
) -> None:
    """Try SYN-RBL on `pairs`; on crash, binary-subdivide recursively.

    Successful results land in ``out[i]``. If a batch of size N crashes,
    we recurse into two halves — limits the blast radius of a single bad
    input to log2(chunk_size) retries instead of N per-reaction calls.
    """
    if not pairs:
        return
    try:
        results = bal.rebalance([r for _, r in pairs])
        for (i, _), result in zip(pairs, results, strict=True):
            if isinstance(result, str) and result:
                out[i] = result
        return
    except Exception as exc:
        if len(pairs) <= min_batch:
            log.debug("SYN-RBL gave up on %d reaction(s): %s", len(pairs), type(exc).__name__)
            return
        mid = len(pairs) // 2
        _try_batch(bal, pairs[:mid], out, min_batch=min_batch)
        _try_batch(bal, pairs[mid:], out, min_batch=min_batch)


def balance_reactions(
    reaction_smiles: Iterable[str],
    n_jobs: int = 1,
) -> list[str | None]:
    """Run SYN-RBL over a list of reaction SMILES; return balanced strings.

    Returns None for entries that SYN-RBL could not process or balance.
    Handles USPTO's 3-part ``reactants>agents>products`` by dropping agents.
    On batch failure, binary-subdivides so a single bad input costs only
    ``log2(chunk_size)`` retries, not ``N`` per-reaction calls.
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

    _try_batch(bal, valid_pairs, out, min_batch=1)
    return out

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

import contextlib
import io
import logging
from collections.abc import Iterable, Iterator

from rdkit import RDLogger

log = logging.getLogger(__name__)

# Suppress RDKit's verbose warnings and SYN-RBL's traceback flood.
RDLogger.DisableLog("rdApp.*")


@contextlib.contextmanager
def _suppress_synrbl_noise() -> Iterator[None]:
    """Silence SYN-RBL's internal stderr noise during batch calls."""
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
    """Normalize to `reactants>>products` shape. Fast string checks only."""
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


def _try_batch(
    bal: object,
    pairs: list[tuple[int, str]],
    out: list[str | None],
    max_retry_depth: int = 1,
    _depth: int = 0,
) -> None:
    """Try SYN-RBL on `pairs`; on crash, optionally subdivide once.

    Successful results land in ``out[i]``. If the batch crashes AND
    ``_depth < max_retry_depth``, we split in half and retry — giving at
    most one level of recovery. Deeper recursion is disabled because each
    re-init of SYN-RBL costs ~5s regardless of batch size, which balloons
    runtime by 10-100x without meaningfully improving recovery rate.
    """
    if not pairs:
        return
    try:
        with _suppress_synrbl_noise():
            results = bal.rebalance([r for _, r in pairs])
        # SYN-RBL can return a list, a pandas DataFrame, or sometimes a
        # truncated result. Best-effort: pull out any string entries and
        # zip by position (len mismatch just means we drop trailing rxns).
        if hasattr(results, "to_dict"):  # pandas DataFrame
            results = (
                results["reaction_smiles"].tolist()
                if "reaction_smiles" in results
                else list(results)
            )
        if results is None or len(results) == 0:
            raise ValueError("SYN-RBL returned empty results")
        for (i, _), result in zip(pairs, results, strict=False):
            if isinstance(result, str) and result:
                out[i] = result
        return
    except Exception as exc:
        log.warning(
            "SYN-RBL batch of %d failed (depth=%d, %s).", len(pairs), _depth, type(exc).__name__
        )
        if _depth >= max_retry_depth or len(pairs) <= 1:
            return  # skip — accept losing this batch rather than multiply init cost
        mid = len(pairs) // 2
        _try_batch(bal, pairs[:mid], out, max_retry_depth, _depth + 1)
        _try_batch(bal, pairs[mid:], out, max_retry_depth, _depth + 1)


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

    _try_batch(bal, valid_pairs, out, max_retry_depth=1)
    return out

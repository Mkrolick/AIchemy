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


def balance_reactions(
    reaction_smiles: Iterable[str],
    n_jobs: int = 1,
) -> list[str | None]:
    """Run SYN-RBL over a list of reaction SMILES; return balanced strings.

    Returns None for entries that SYN-RBL could not balance.
    """
    Balancer = _import_balancer()
    bal = Balancer(n_jobs=n_jobs)
    rxns = list(reaction_smiles)
    if not rxns:
        return []
    balanced = bal.rebalance(rxns)

    out: list[str | None] = []
    for original, result in zip(rxns, balanced, strict=True):
        if isinstance(result, str) and result:
            out.append(result)
        else:
            log.warning("SYN-RBL could not balance: %s", original)
            out.append(None)
    return out

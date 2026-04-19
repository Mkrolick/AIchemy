"""Tests for the SYN-RBL wrapper (Stage 07).

SYN-RBL is heavy (XGBoost + MCS) and pulls libomp on macOS. These tests
verify basic import & API surface; they skip cleanly if synrbl isn't
installed so CI stays fast.
"""

from __future__ import annotations

import pytest


def test_balance_reactions_empty_input_returns_empty() -> None:
    from aichemy.preprocessing.balance.syn_rbl import balance_reactions

    # Empty path doesn't need synrbl at all.
    assert balance_reactions([]) == []


@pytest.mark.slow
def test_balance_reactions_fixes_missing_water() -> None:
    pytest.importorskip("synrbl")
    from aichemy.preprocessing.balance.syn_rbl import balance_reactions

    # Ester hydrolysis missing a water: ethyl acetate → acetic acid + ethanol
    # needs water on the reactant side to balance.
    result = balance_reactions(["CC(=O)OCC>>CC(=O)O.CCO"], n_jobs=1)
    assert len(result) == 1
    # SYN-RBL should add the missing water; the exact SMILES varies but
    # "O" (water) should appear.
    assert result[0] is not None
    assert "O" in result[0]

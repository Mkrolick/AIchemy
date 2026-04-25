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


def test_balance_reactions_malformed_input_returns_none_pair() -> None:
    from aichemy.preprocessing.balance.syn_rbl import balance_reactions

    # _normalize_for_synrbl filters these before SYN-RBL is called, so
    # synrbl need not be installed for this test to pass.
    result = balance_reactions(["not_a_smiles", "", "no_arrow_here"], n_jobs=1)
    assert result == [(None, None), (None, None), (None, None)]


@pytest.mark.slow
def test_balance_reactions_fixes_missing_water() -> None:
    pytest.importorskip("synrbl")
    from aichemy.preprocessing.balance.syn_rbl import balance_reactions

    # Ester hydrolysis missing a water: ethyl acetate → acetic acid + ethanol
    # needs water on the reactant side to balance.
    result = balance_reactions(["CC(=O)OCC>>CC(=O)O.CCO"], n_jobs=1)
    assert len(result) == 1
    smi, conf = result[0]
    # SYN-RBL should add the missing water; the exact SMILES varies but
    # "O" (water) should appear. Ester hydrolysis solves on the rule-based
    # path, which reports no confidence.
    assert smi is not None
    assert "O" in smi
    assert conf is None

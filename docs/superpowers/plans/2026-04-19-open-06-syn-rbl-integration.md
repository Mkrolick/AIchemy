# Open Item 06 — SYN-RBL integration

**Goal:** Install and verify SYN-RBL for USPTO atom-balancing (Stage 07).

**Unblocks:** Stage 07 (balance uspto).

## Tasks

- [ ] Research install path: `pip install syn-rbl`, or from GitHub source, or via conda
- [ ] Verify Python 3.11 compatibility
- [ ] Verify RDKit version compatibility (our runtime uses rdkit>=2024.3)
- [ ] Run a 5-minute benchmark on ~100 USPTO reactions from the Lowe fixture — confirm runtime is acceptable (<5s per reaction)
- [ ] Document any required system deps (e.g., OpenBabel)
- [ ] Add to `pyproject.toml` dependencies once verified
- [ ] Commit updated Stage 07 plan noting "unblocked"

**Fallback if SYN-RBL proves impractical:** use RDKit's built-in `Chem.rdChemReactions.RunReactantInPlace` with `BalanceReaction` atom-mapping (less sophisticated but self-contained).

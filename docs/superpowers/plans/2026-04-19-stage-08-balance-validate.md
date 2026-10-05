# Stage 08 — balance validate

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 08 COMPLETE`.

**Goal:** Universal atom-count validation for **all** reactions (MetaNetX + USPTO, post-SYN-RBL). Populate `balanced: bool` on every row. Catches MetaNetX curation gaps (missing protons, implicit waters) that the proposal flags.

**Architecture:** `aichemy.preprocessing.balance.validate.is_balanced(reactants: list[Stoichiometry], products: list[Stoichiometry], molecules: dict[str, str]) -> bool` computes sum of atoms on each side using RDKit and returns True iff they match for every element. Allow a configurable tolerance for protons (MetaNetX convention often elides H+).

## Tasks

### T1: `atom_counts(smiles, coefficient) -> Counter[str]`
- [ ] Failing test: `atom_counts("CCO", 1.0)` → `{"C": 2, "H": 6, "O": 1}`; `atom_counts("CCO", 2.0)` → all counts doubled
- [ ] Implement using RDKit `GetAtomsWithH()` — explicit H add
- [ ] Commit

### T2: `is_balanced` core
- [ ] Failing test: balanced reaction returns True, unbalanced returns False
- [ ] Failing test: MetaNetX-style with missing protons — returns True when `ignore_elements=["H"]` (configurable), False otherwise
- [ ] Commit

### T3: `validate_reactions(df, molecules, config)` orchestrator
- [ ] Failing integration test: input reactions parquet, output same schema with `balanced` column populated per row
- [ ] Commit

### T4: Wire CLI + verify with `dvc repro balance_validate`
- [ ] Commit + push

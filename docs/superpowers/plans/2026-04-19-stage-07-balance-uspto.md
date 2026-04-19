# Stage 07 — balance uspto (SYN-RBL)

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 07 COMPLETE`.
> **Blocks on:** Open Item 06 (SYN-RBL install/compatibility verification).

**Goal:** For USPTO reactions only, attempt atom-mapped balancing via SYN-RBL; drop reactions that cannot be balanced, normalize non-integer stoichiometric coefficients by multiplying through the LCD, persist `balanced: bool` column.

**Status:** Stub writes empty parquet. SYN-RBL not yet installed.

**Architecture:** `aichemy.preprocessing.balance.syn_rbl` wraps the SYN-RBL Python API (once available): given a raw reaction SMILES, return `(success: bool, balanced_smiles: str | None, reactants: list[Stoichiometry], products: list[Stoichiometry])`. The stage filter drops rows where `success=False`.

## Tasks

### T1 (BLOCKED): Verify SYN-RBL install

- [ ] Install SYN-RBL (`pip install syn-rbl` or from source) — may require specific RDKit version
- [ ] Write minimal smoke test: import, call on a known-balanceable reaction, verify result
- [ ] If install fails, document exact error + required resolution

### T2: Wrapper function

- [ ] Failing test (skipped unless SYN-RBL installed): `balance_reaction(rxn_smiles)` on known balanceable reaction returns success=True with integer coefficients
- [ ] Failing test: on a deliberately unbalanced reaction, returns success=False
- [ ] Implement wrapper
- [ ] Commit

### T3: LCD normalization

- [ ] Failing test: wrapper given `0.5 A + B -> 0.5 C` should normalize to `A + 2 B -> C` (multiplied through 2)
- [ ] Implement: if any coefficient is non-integer, multiply all by LCD (using `math.lcm` over denominators from `fractions.Fraction.from_float(...).limit_denominator(100)`)
- [ ] Commit

### T4: Stage orchestrator

- [ ] Failing integration test: input reactions with mix of USPTO and MetaNetX; output contains all MetaNetX rows pass-through and balanceable USPTO rows, drops unbalanceable
- [ ] Implement: filter `source == "uspto"`, apply wrapper, re-merge with MetaNetX rows
- [ ] Commit

### T5: CLI + DVC

- [ ] Wire CLI to orchestrator; integration smoke
- [ ] Commit + push

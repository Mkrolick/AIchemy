# Open Item 03 — eQuilibrator ΔG'° integration

**Goal:** Optionally enrich MetaNetX reactions with computed ΔG'° (standard transformed Gibbs free energy) from eQuilibrator.

**Current state:** Stage 11 (directionality) uses only MetaNetX's directionality flag as a thermodynamic proxy. `delta_g` column is nullable.

**When to do this:** Once the MILP (Open Item 07) is running and we see whether directionality alone is sufficient. If the solver is picking thermodynamically unfavorable reactions, wire eQuilibrator.

## Tasks (Ralph loop: 30 iterations when activated)

- [ ] Add `equilibrator-api` to dependencies
- [ ] Create `aichemy.preprocessing.augment.thermo` module
- [ ] Implement `compute_delta_g(reaction_smiles, ph, ionic_strength) -> float | None`
- [ ] Add `config.thermo.equilibrator.{enabled, ph, ionic_strength}` config
- [ ] Write `augment_thermo(df, config)` that populates `delta_g` column for enzymatic reactions
- [ ] Add `augment_thermo` as a new CLI subcommand + DVC stage after `augment_directionality`
- [ ] Tests with record/replay for eQuilibrator API calls

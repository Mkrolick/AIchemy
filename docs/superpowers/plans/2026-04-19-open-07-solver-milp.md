# Open Item 07 — MILP Solver Package (`aichemy.solver`)

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `SOLVER MVP COMPLETE`.

**Goal:** Implement the MILP formulation from the proposal as a sibling package `src/aichemy/solver/` consuming `data/processed/{reactions,molecules}.parquet`.

**Prerequisites:** Stages 02–12 must produce a reasonable processed hypergraph first. Solver is useless without real data.

**MVP scope (first-pass):**
- LP version only (no binary decision variables) — lightweight, easier to validate
- Objective: maximize `Σ w_m π_m q_m^sell − Σ π_m q_m^buy`
- Constraints: mass balance per molecule
- No fixed reaction costs, no cardinality limit (leave for MILP v2)
- Gurobi backend via `gurobipy`

## Tasks

### T1: Package scaffolding
- [ ] Create `src/aichemy/solver/{__init__.py, model.py, cli.py, io.py}`
- [ ] Add `solver` entry point subcommand
- [ ] Register in pyproject.toml scripts

### T2: Config
- [ ] New `SolverConfig` Pydantic model: `budget`, `num_sellable_products_cap`, `min_flow`, `solver_backend: Literal["gurobi", "cbc"]`
- [ ] Extend `configs/default.yaml` with a `solver` section

### T3: Problem builder
- [ ] `build_model(reactions_df, molecules_df, config) -> gp.Model`
- [ ] Variables: `f_r` flow per reaction, `q_buy_m`, `q_sell_m` per molecule
- [ ] Mass balance constraint per molecule
- [ ] Objective: profit = sum(prices * sells) − sum(prices * buys)
- [ ] Budget constraint

### T4: Solve + report
- [ ] `solve(model) -> dict` returning selected reactions, products, flows, objective value
- [ ] `report(solution, output_path)` writes a JSON summary

### T5: CLI
- [ ] `aichemy solver run --config configs/default.yaml`
- [ ] DVC stage `solve` consuming processed parquets + emitting solution.json

### T6: MILP v2 extension (separate Ralph loop)
- [ ] Binary `y_r` variables (reaction activation)
- [ ] Cardinality constraint on sellable products
- [ ] Fixed activation costs per reaction

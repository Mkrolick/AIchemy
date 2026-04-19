# AIchemy Repo Layout — Design Spec

**Date:** 2026-04-19
**Status:** Approved (brainstorm complete; implementation plan pending)
**Scope:** Repository structure and tooling for the AIchemy preprocessing pipeline, designed to accommodate a future MILP solver sub-package without restructuring.

## Context

AIchemy answers the question: *"Given material market prices, what should I make to maximize profit margins using chemo-enzymatic reactions?"* It formulates chemical synthesis planning as a profit-maximization MILP over a hypergraph of chemicals (nodes) and reactions (edges). The preprocessing pipeline prepares this hypergraph by merging two open-source reaction databases (MetaNetX for enzymatic, USPTO for chemical) and deriving the parameters the solver consumes (stoichiometry, yield, price, ΔG').

This spec covers repo layout and tooling only; the pipeline's scientific content and the MILP formulation are covered in `gdocs_proposal.md`.

## Decisions

The following calls were made during brainstorming and are load-bearing for this design:

| Decision | Choice | Rationale |
|---|---|---|
| Repo scope | Preprocessing now, solver/scrapers later as sibling sub-packages | Research projects accrete; a sub-package layout costs nothing upfront and avoids a painful rename later |
| Dependency tooling | uv + `pyproject.toml` + `uv.lock` | Fast, modern, single source of truth |
| Data residency | Local directory + DVC with local remote (Git-LFS-style) | No cloud billing; versioned data artifacts; swap-in S3/GCS later without touching `dvc.yaml` |
| Invocation style | Hybrid: CLI (`aichemy ...`) drives the pipeline, notebooks are scratch space | CLI pairs with DVC stages; notebooks remain useful for exploration |
| Config management | Pydantic models + YAML files with override layering | Typed, introspectable, YAML diffs track well in git |
| DataFrame library | Polars by default, pandas only at notebook display boundaries | 2-3x faster at USPTO scale (~1-3M reactions), lazy evaluation, Arrow-backed zero-copy conversion |
| Schema validation | `patito` (Polars-native schema validation on Pydantic) | Catches schema drift early without pandera's pandas-first assumptions |
| Preprocessing internal split | Split-by-concern (`sources/`, `chem/`, `dedup/`, `balance/`, `augment/`) | Chemistry primitives reusable across sources; dedup naturally merges-then-reduces |

## Architecture

### Top-level directory structure

```
AIchemy-fresh/
├── .github/workflows/ci.yml        # minimal CI: ruff, mypy, pytest
├── configs/
│   ├── default.yaml                # base config — all knobs
│   └── profiles/
│       ├── strict_dedup.yaml       # overrides: tight Tanimoto
│       └── mean_yields.yaml        # overrides: yield imputation strategy
├── data/                           # gitignored, DVC-tracked
│   ├── raw/                        # unprocessed downloads (MetaNetX, USPTO)
│   ├── interim/                    # per-stage artifacts
│   └── processed/                  # final deliverables for the solver
├── docs/
│   └── superpowers/specs/          # design docs (this file)
├── notebooks/                      # scratch exploration, outputs stripped by nbstripout
├── src/
│   └── aichemy/
│       ├── __init__.py
│       ├── cli.py                  # Typer entry point; subcommands map 1:1 to DVC stages
│       ├── config.py               # Pydantic config models + YAML loader + override layering
│       └── preprocessing/          # see next section
├── tests/
│   ├── conftest.py
│   ├── fixtures/                   # tiny hand-picked sample data
│   ├── unit/                       # pure-function tests
│   └── integration/                # end-to-end on fixtures, CLI smoke tests
├── dvc.yaml                        # pipeline stage definitions
├── dvc.lock                        # generated, tracked
├── pyproject.toml                  # uv-managed
├── uv.lock                         # generated, tracked
├── .pre-commit-config.yaml         # ruff + nbstripout
├── .gitignore
├── .dvcignore
├── README.md
└── gdocs_proposal.md               # existing proposal, retained
```

### Package structure: `src/aichemy/preprocessing/`

```
preprocessing/
├── __init__.py
├── pipeline.py                     # programmatic API (for notebooks/tests); NOT a CLI orchestrator — dvc repro is canonical
├── io.py                           # Polars parquet I/O + path resolution (AICHEMY_DATA_DIR)
├── normalize.py                    # merge sources + canonical SMILES + hydrocarbon filter → unified tables
│
├── sources/                        # raw data ingestion
│   ├── __init__.py
│   ├── metanetx.py                 # reac_prop, chem_prop, xrefs → polars DataFrames
│   └── uspto.py                    # Lowe dataset → polars DataFrame
│
├── chem/                           # chemistry primitives (reusable across sources)
│   ├── __init__.py
│   ├── smiles.py                   # canonicalize, parse, is_valid
│   ├── similarity.py               # morgan fingerprint, tanimoto, bulk + Butina clustering
│   ├── filters.py                  # carbon_count, has_hydrocarbon_reactant_and_product
│   └── identifiers.py              # InChIKey, MetaNetX ID resolution
│
├── dedup/
│   ├── __init__.py
│   ├── molecules.py                # primary: InChIKey equality; secondary: Tanimoto=1.0 collision check; emits old→canonical mol_id map
│   └── reactions.py                # canonical-SMILES hash → Tanimoto cluster; rewrites reactant/product mol_ids via the dedup map
│
├── balance/
│   ├── __init__.py
│   ├── validate.py                 # universal: RDKit atom-count check → populates balanced: bool on all reactions (MetaNetX + USPTO)
│   └── syn_rbl.py                  # USPTO-specific: SYN-RBL attempt-at-balance; runs before validate
│
└── augment/
    ├── __init__.py
    ├── yields.py                   # global_mean / per_ec / fixed imputation strategies
    ├── prices.py                   # ChemPrize via PriceLookup protocol (stub available for tests)
    └── directionality.py           # MetaNetX directionality flag → forward-only reactions (proxy for thermodynamic favorability)
```

**Split-by-concern rationale.** Chemistry primitives (canonicalization, Tanimoto, carbon counting) are source-agnostic and belong in `chem/`. Ingestion is source-specific and lives in `sources/`. `normalize.py` owns the merge step: it reads both raw source parquets and produces a single unified `molecules`/`reactions` pair on a common schema, applying canonical SMILES and the hydrocarbon filter along the way. Dedup then operates on the merged post-normalization dataset — giving it its own subpackage lets molecule-dedup and reaction-dedup share chemistry utilities without entangling source-specific parsing. Augmentation stages (yields, prices, directionality) operate on the full merged table and are independent of source.

Alternatives considered: split-by-source (duplicates chemistry utilities); split-by-pipeline-stage (files get too large, primitives get buried as helpers). Neither provides the reuse + isolation that split-by-concern gives.

**Dedup identity contract.** Molecule dedup is authoritative: it picks the canonical `mol_id` for each equivalence class (MetaNetX ID when any source contributes one, else InChIKey), and emits a `dedup_map: dict[str, str]` mapping every pre-dedup `mol_id` to its canonical ID. Reaction dedup (and the export stage) applies this map to rewrite all reactant/product `mol_id` references. After this step, every `mol_id` referenced from `reactions.parquet` is guaranteed to resolve to a row in `molecules.parquet`. A post-dedup integrity check asserts this invariant and fails the stage if violated.

**Molecule identity test.** Primary check is canonical SMILES / InChIKey equality; this is the gold standard and should catch ~all structural duplicates post-canonicalization. Tanimoto=1.0 on 2048-bit Morgan fingerprints runs as a secondary consistency check — fingerprint collisions exist, so Tanimoto alone is not sufficient for identity, but matching Tanimoto with mismatched InChIKey flags canonicalization bugs worth investigating.

### Data contracts

Two core tables flow through the pipeline, written as Polars-compatible parquet files:

**`molecules.parquet`:**
- `mol_id: str` — MetaNetX ID where available, else canonical InChIKey
- `canonical_smiles: str`
- `inchi_key: str`
- `carbon_count: int`
- `price_per_gram: float | None` — populated by `augment.prices`
- `source_refs: list[str]` — original IDs in each source database

**`reactions.parquet`:**
- `rxn_id: str`
- `reaction_smiles: str`
- `reactants: list[struct{mol_id: str, coefficient: float}]`
- `products: list[struct{mol_id: str, coefficient: float}]`
- `type: enum{enzymatic, chemical}`
- `yield_rate: float` — named `yield_rate` rather than `yield` because `yield` is a Python keyword; renaming avoids field-alias machinery in patito
- `delta_g: float | None` — nullable; non-null only for enzymatic where relevant
- `balanced: bool` — populated by `balance/validate.py` for all reactions (MetaNetX + USPTO), not only successfully SYN-RBL'd USPTO rows
- `source: enum{metanetx, uspto}`

**Coefficient semantics.** `coefficient` is stored as `float` for parquet-schema simplicity, but post-balance coefficients are *expected to be integer-valued* (non-integer stoichiometry would indicate a half-reaction or an unnormalized balancer output). `balance/validate.py` enforces this: if SYN-RBL emits a non-integer coefficient for a USPTO reaction, the balancer multiplies through the least common denominator before emitting; if that fails, the reaction is marked `balanced=False`. For MetaNetX, coefficients are already integer in the source data. The downstream MILP solver can therefore assume integer coefficients when formulating mass-balance constraints.

Schemas declared as `patito` models in `aichemy.preprocessing.io`, validated at stage boundaries (after ingest, after normalize, after dedup, after balance, before export).

### Pricing adapter

ChemPrize access is an open dependency (licensing/API details unresolved at spec time). To avoid blocking on it:

```python
class PriceLookup(Protocol):
    def lookup(self, smiles: str) -> float | None: ...

class ChemPrizeClient(PriceLookup): ...   # real implementation, written when access resolves
class StubPriceLookup(PriceLookup): ...   # returns fixed / tabulated prices for tests and early dev
```

`augment.prices` takes a `PriceLookup` in its constructor. A small factory (`augment.prices.make_lookup(config) -> PriceLookup`) selects the implementation based on `prices.backend` (`chemprize` vs. `stub`); both the CLI subcommand and `pipeline.run_all` use this factory, so the two invocation paths stay consistent. This keeps the pipeline runnable end-to-end with stub prices while ChemPrize integration proceeds in parallel.

## Config

### Model (`src/aichemy/config.py`)

Pydantic v2 models define every knob with types and defaults. Example shape:

```python
class DedupConfig(BaseModel):
    tanimoto_threshold: float = 1.0
    reaction_tanimoto_threshold: float = 0.95
    fingerprint_radius: int = 2
    fingerprint_bits: int = 2048

class FilterConfig(BaseModel):
    min_carbon_count: int = 2                 # "> 1 carbon" per proposal

class YieldImputationStrategy(str, Enum):
    GLOBAL_MEAN = "global_mean"
    PER_EC_CLASS = "per_ec_class"
    FIXED = "fixed"

class YieldConfig(BaseModel):
    strategy: YieldImputationStrategy = YieldImputationStrategy.GLOBAL_MEAN
    fixed_value: float = 0.85
    enzymatic_prior_range: tuple[float, float] = (0.85, 0.95)

class SourcesConfig(BaseModel):
    metanetx_version: str = "4.4"
    uspto_slice: Literal["grants_1976_2016", "full"] = "grants_1976_2016"

class PathsConfig(BaseModel):
    data_dir: Path = Path("data")             # overridable via AICHEMY_DATA_DIR env

class PricesConfig(BaseModel):
    backend: Literal["chemprize", "stub"] = "stub"

class PreprocessingConfig(BaseModel):
    sources: SourcesConfig = SourcesConfig()
    filter: FilterConfig = FilterConfig()
    dedup: DedupConfig = DedupConfig()
    yields: YieldConfig = YieldConfig()
    prices: PricesConfig = PricesConfig()
    paths: PathsConfig = PathsConfig()
```

### Loader

```python
def load_config(path: Path, overrides: list[Path] = ()) -> PreprocessingConfig:
    """Load base YAML, deep-merge each override in order, validate via Pydantic."""
```

Override files contain only the keys they modify. Last override wins.

**Deep-merge semantics** (pinned to avoid subtle bugs):
- **Dict-valued keys**: recursively merged (override keys are added / existing keys are replaced at leaf).
- **Scalar-valued keys**: replaced wholesale.
- **List- and tuple-valued keys**: *replaced* wholesale, never concatenated. An override specifying `yields.enzymatic_prior_range: [0.9, 0.95]` replaces the base `[0.85, 0.95]` in full.

This is tested explicitly in `tests/unit/test_config.py` including the list-replacement case.

### CLI (Typer)

Each subcommand wraps a single pipeline stage: load config → call stage function → write parquet.

```
aichemy fetch-raw             --config configs/default.yaml
aichemy ingest metanetx       --config configs/default.yaml
aichemy ingest uspto          --config configs/default.yaml
aichemy normalize             --config configs/default.yaml
aichemy dedup molecules       --config configs/default.yaml
aichemy dedup reactions       --config configs/default.yaml
aichemy balance uspto         --config configs/default.yaml   # SYN-RBL reconstruction
aichemy balance validate      --config configs/default.yaml   # universal atom-count check → balanced: bool
aichemy augment yields        --config configs/default.yaml
aichemy augment prices        --config configs/default.yaml
aichemy augment directionality --config configs/default.yaml
aichemy export                --config configs/default.yaml
```

CLI subcommands take `--config path` and repeatable `--override path` flags.

**No `aichemy pipeline run` subcommand.** End-to-end pipeline execution is owned by `dvc repro`, which is the single canonical orchestrator: it tracks dependencies, skips unchanged stages, and versions outputs. `preprocessing/pipeline.py` exists as a *programmatic* API — functions like `run_all(config) -> ProcessedTables` callable from notebooks and integration tests — but has no CLI surface. This keeps there from being two drift-prone paths to "run the whole thing."

## DVC Integration

One DVC stage per CLI subcommand. Each stage declares its source-code deps (so refactors inside a stage invalidate its cache), config deps (so knob changes invalidate downstream), and input/output parquet paths.

```yaml
stages:
  fetch_raw:
    cmd: uv run aichemy fetch-raw --config configs/default.yaml
    deps: [configs/default.yaml]
    outs:
      - data/raw/metanetx/
      - data/raw/uspto/

  ingest_metanetx:
    cmd: uv run aichemy ingest metanetx --config configs/default.yaml
    deps:
      - configs/default.yaml
      - src/aichemy/preprocessing/sources/metanetx.py
      - data/raw/metanetx/
    outs:
      - data/interim/metanetx/reactions_raw.parquet
      - data/interim/metanetx/molecules_raw.parquet

  # ingest_uspto, normalize, dedup_molecules, dedup_reactions,
  # balance_uspto, balance_validate, augment_yields, augment_prices,
  # augment_directionality, export — same shape, chained via parquet paths
```

**Stage ordering constraint.** `balance_uspto` (SYN-RBL reconstruction) runs *before* `balance_validate` (universal atom-count check). SYN-RBL gets a chance to fix USPTO rows first; `balance_validate` then computes the `balanced: bool` column for every reaction across both sources. MetaNetX reactions skip SYN-RBL entirely but are still validated — catching known curation gaps (missing protons, implicit waters) rather than silently trusting MetaNetX's pre-curation.

### DVC remote (local, Git-LFS-style)

```bash
dvc remote add -d local_store ~/aichemy-dvc-storage
# .dvc/config.local holds the user-specific path; gitignored.
# .dvc/config holds the shared remote name only.
```

A collaborator or future machine sets their own `local_store` path and `dvc pull`s. Migration to S3/GCS = swap the remote URL; `dvc.yaml` unchanged.

### Data layering

- `data/raw/` — verbatim downloads, never modified
- `data/interim/` — per-stage outputs; `dvc repro` regenerates on demand
- `data/processed/` — final hypergraph parquets + `hypergraph_manifest.json`

`.gitignore` excludes `data/`. DVC pointer files (`data/raw.dvc`, etc.) are committed.

## Testing

### Structure

```
tests/
├── conftest.py
├── fixtures/
│   ├── metanetx_sample/            # ~20 hand-picked reactions across representative EC classes
│   │   ├── reac_prop.tsv
│   │   ├── chem_prop.tsv
│   │   └── reac_xref.tsv
│   ├── uspto_sample/               # ~20 reaction SMILES with known balance/yield
│   └── known_duplicates.csv        # molecule pairs with expected dedup behavior
├── unit/
│   ├── test_smiles.py              # canonicalization, parse edge cases, invalid input
│   ├── test_similarity.py          # identical → 1.0; known pairs; fingerprint determinism
│   ├── test_filters.py             # carbon count with aromatic rings, H2O exclusion
│   ├── test_normalize.py           # merge semantics: duplicate IDs across sources, schema unification
│   ├── test_dedup_molecules.py     # InChIKey primary; Tanimoto=1.0 collision check; dedup_map construction
│   ├── test_dedup_reactions.py     # canonical-SMILES hash + Tanimoto cluster; mol_id rewriting via dedup_map
│   ├── test_balance_validate.py    # atom-count check: known balanced/unbalanced cases, MetaNetX proton/water gaps
│   ├── test_yield_imputation.py    # each strategy in isolation
│   └── test_config.py              # YAML load + override layering + list-replace semantics + Pydantic validation
└── integration/
    ├── test_metanetx_end_to_end.py # fixture → full pipeline → asserted output schema and counts
    ├── test_referential_integrity.py # every reactions' mol_id resolves in molecules.parquet post-dedup
    └── test_cli_smoke.py           # CLI subcommands succeed on fixture inputs
```

### Strategy

- Unit tests target pure functions in `chem/` (including `chem/filters.py`), `dedup/` (including the mol_id rewrite contract), `normalize.py`, `balance/validate.py`, `augment/yields.py`, and `config.py` (including list-replace override semantics).
- Integration tests run the full pipeline on fixture directories, asserting schemas, row counts, and the dedup referential-integrity invariant (every reactions' `mol_id` resolves in `molecules.parquet`).
- Prices use `StubPriceLookup`. ChemPrize is not exercised in CI.
- No test hits the live MetaNetX or USPTO downloads; all raw inputs are fixture files.

## Tooling

### `pyproject.toml`

```toml
[project]
name = "aichemy"
version = "0.0.1"
requires-python = ">=3.11"
dependencies = [
    "polars>=1.0",
    "rdkit>=2024.3",
    "pydantic>=2.6",
    "patito>=0.8",
    "typer>=0.12",
    "pyyaml>=6.0",
    "numpy",
    "scipy",
]

[project.optional-dependencies]
solver    = ["gurobipy>=11.0"]                # reserved for the future MILP sub-package
notebooks = ["jupyter", "pandas", "matplotlib"]

[project.scripts]
aichemy = "aichemy.cli:app"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-cov",
    "ruff>=0.4",
    "mypy>=1.10",
    "pre-commit",
    "nbstripout",
    "dvc>=3.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.mypy]
strict = true
files = ["src/aichemy"]
```

### Pre-commit

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/kynan/nbstripout
    rev: 0.7.1
    hooks:
      - id: nbstripout
```

### CI (GitHub Actions, minimal)

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-extras
      - run: uv run ruff check .
      - run: uv run mypy src/
      - run: uv run pytest
```

CI uses fixture data only; it does not contact DVC remotes or external services.

## Future Extension Points

These are not part of this spec's scope but shape the design:

- **`src/aichemy/solver/`** — MILP formulation over the hypergraph, using `gurobipy`. Will consume `data/processed/{reactions,molecules}.parquet` and config sections not yet defined (`configs/solver/`). Can rely on integer-valued stoichiometric coefficients per the contract in Data Contracts.
- **`src/aichemy/scrapers/`** — patent-filing scrapers for fixed costs and stoichiometry augmentation, per the proposal's Todos section.
- **`src/aichemy/eval/`** — benchmarking the MILP's output against known profitable products.
- **`augment/thermo.py`** — eQuilibrator API integration for computed ΔG'°. Would populate `delta_g` for MetaNetX reactions where currently only the directionality flag is used. Lands as a sibling to `augment/directionality.py`; neither replaces the other.
- **S3 DVC remote migration** — swap `local_store` URL; `dvc.yaml` unchanged.
- **Real ChemPrize integration** — implement `ChemPrizeClient(PriceLookup)`; no other module changes.

## Open Questions Deferred to Implementation

1. ChemPrize API/licensing access — unblocks `augment.prices` real implementation.
2. USPTO slice commitment — `grants_1976_2016` is the default, but full-application scope is configurable.
3. ΔG' enrichment for MetaNetX — this spec uses `augment/directionality.py` only (trust MetaNetX's directionality flag). A future `augment/thermo.py` can layer eQuilibrator ΔG'° on top without replacing directionality.
4. Raw-data download URLs for `fetch_raw` stage — pinned in config, manual override via local files documented in README.
5. MetaNetX atom-balance failure handling — `balance/validate.py` will identify unbalanced MetaNetX rows (proton/water curation gaps); initial policy is to mark `balanced=False` and pass them through with that flag visible to the solver (which can then optionally exclude them). Whether to attempt automated patching (e.g., proton-balancing heuristics) is a follow-up decision once we have a sense of how many rows are affected.

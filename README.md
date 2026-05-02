# AIchemy

Profit-maximizing chemo-enzymatic reaction pathway selection via MILP over a unified hypergraph of MetaNetX (enzymatic) and USPTO (chemical) reactions.

The pipeline is orchestrated with [DVC](https://dvc.org): each stage (ingest, normalize, dedup, balance, augment, patents, select, export, MW augmentation) is declared in `dvc.yaml`, dependency hashes live in `dvc.lock`, and bulk data + intermediate parquets are versioned through a configurable DVC remote — only small text artifacts are committed to git.

See `proposal.md` for the scientific motivation. See `docs/superpowers/specs/` for engineering design docs.

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)

### Setup

```bash
# Clone and install
git clone https://github.com/mkrolick/AIchemy.git
cd AIchemy
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Configure your local DVC remote (pick any path you have write access to)
mkdir -p ~/aichemy-dvc-storage
uv run dvc remote modify --local local_store url ~/aichemy-dvc-storage
```

### Run the pipeline

```bash
uv run dvc repro
```

This executes every stage in the DAG and produces the unified hypergraph at `data/processed/{reactions,molecules}.parquet`, plus the MW-augmented molecule table consumed by the solver. `uv run dvc dag` renders the stage graph.

### Run tests and lints

```bash
uv run pytest              # tests
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy src/           # typecheck
```

### Reproducibility — lock files

Both `uv.lock` (Python dependency graph) and `dvc.lock` (per-stage input/output hashes) are committed to git and pushed with the repo. `uv sync` installs the exact resolved versions from `uv.lock`, and `dvc repro` skips any stage whose dependencies haven't changed by hash. Don't gitignore either file: dropping `uv.lock` makes installs non-deterministic, and dropping `dvc.lock` forces every stage to re-run on every checkout.

## Project Layout

```
src/aichemy/
├── cli.py                  # Typer entry point
├── config.py               # Pydantic config models + YAML loader
├── preprocessing/
│   ├── io.py               # Polars parquet I/O + patito schemas
│   ├── pipeline.py         # programmatic API (not the CLI)
│   ├── normalize.py        # merge + canonicalize + filter
│   ├── select.py           # post-augmentation reaction curation
│   ├── export.py           # final hypergraph + manifest emit
│   ├── sources/            # MetaNetX, USPTO ingestion
│   ├── chem/               # SMILES, similarity, filters, identifiers
│   ├── dedup/              # molecule + reaction deduplication
│   ├── balance/            # SYN-RBL + RDKit atom-count validation
│   ├── augment/            # yields, thermo, directionality, prices,
│   │                       #   licenses, molecule_weights, yields_thermo
│   └── patents/            # patent metadata fetch + CPC/LLM license classify
├── solver/                 # MILP profit-maximization (PuLP, CBC/Gurobi)
├── eval/                   # solver-vs-baseline evaluation harnesses
└── scrapers/               # vendor pricing scrapers (used by aichemy-pricing)

configs/
├── default.yaml            # base config — all knobs
├── subset.yaml             # smoke-test config for the data_subset/ fixtures
├── cpc_rules.yaml          # CPC-code → license-class mapping
└── profiles/               # named overrides (strict_dedup, mean_yields)

tests/
├── unit/                   # pure-function tests
├── integration/            # end-to-end + CLI smoke + solver validation
└── fixtures/               # sample data
```

## Configuration

All pipeline knobs live in `configs/default.yaml`. Apply one or more profile overrides at invocation:

```bash
uv run aichemy dedup reactions \
    --config configs/default.yaml \
    --override configs/profiles/strict_dedup.yaml
```

Override semantics: dict-valued keys deep-merge; scalars and lists are **replaced**, not concatenated.

## Pipeline Orchestration

`dvc repro` is the canonical way to run the pipeline — it tracks dependencies and skips unchanged stages. `aichemy <subcommand>` runs a single stage directly (no dependency tracking). `preprocessing/pipeline.py` provides a programmatic API for notebooks and tests; it has no CLI surface.

Top-level CLI groups: `fetch-raw`, `ingest`, `normalize`, `dedup`, `balance`, `augment`, `patents`, `select`, `export`, `solve`. Run `uv run aichemy <group> --help` for the per-group subcommands.

## Solve

After `dvc repro` populates `data/processed/`, run the MILP profit-maximization solver:

```bash
uv run aichemy solve run --config configs/default.yaml
uv run aichemy solve sweep --config configs/default.yaml   # (r_process, r_comp) grid
```

The mass balance is gram-coherent: stoichiometric coefficients are pre-multiplied by each participant's molecular weight (from `data/processed/molecules_with_mw.parquet`) so reaction extent `f_r` is in mol-extent units while purchase/sale quantities are in grams. Reactions whose participants lack a usable MW are dropped at model-build time with a tally logged. See `src/aichemy/solver/model.py` for the formulation.

## Documentation

- `proposal.md` — scientific proposal (MILP formulation, database choices, solver approach)
- `docs/superpowers/specs/` — design specs (repo layout, pricing/licensing)
- `docs/superpowers/plans/` — implementation plans for each stage and feature

## Vendor pricing

`aichemy-pricing` is a standalone package (sibling to `aichemy`) that resolves
chemical identifiers to per-gram prices via a tiered chain of verified vendor
sources, then converts to USD via a static FX table.

**Install + verify:**
```bash
uv sync --extra pricing
uv run aichemy-price --version
```

**Single-SKU debugging (direct-HTTP vendor classes):**
```bash
uv run aichemy-price lookup fluorochem F765353-1G
uv run aichemy-price lookup molbase 50-78-2 --json
```

`lookup` instantiates a single vendor class. Four classes exist —
`fluorochem`, `molbase`, `medchemexpress`, `tocris` — but `tocris` is
currently broken (page restructured; parser keys are gone) and is excluded
from the default chain. Use it only for parser development.

**Try every vendor through the default chain:**
```bash
uv run aichemy-price chain F765353-1G
```

`chain` runs `build_default_chain`: Fluorochem (L1, Azure-blob JSON) →
Molbase (L1, SSR HTML) → MedChemExpress (L2, curl_cffi for Cloudflare) →
Browserbase Fetch (L3a, ChemCruz parser only). The Browserbase **Browser
API** tier (L3b, where the Enamine parser lives) is **disabled in the
default chain** — it cost ~10s per fall-through at scale; re-enable once
a per-vendor gate is in place. `BROWSERBASE_API_KEY` must be set for the
Fetch path to do anything; otherwise it no-ops.

**InChIKey -> price (offline JOIN + scrape):**
```bash
uv run aichemy-price resolve BSYNRYMUTXBXSQ-UHFFFAOYSA-N \
    --catalog-dir data/raw/pubchem_substance/
```

**Use as an AIchemy backend:**
```yaml
# configs/default.yaml
prices:
  backend: aichemy_pricing
  aichemy_pricing:
    catalog_dir: data/raw/pubchem_substance
    cache_path: data/interim/aichemy_pricing_cache.sqlite
```

The implementation plan and verification trail live at:
- `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md` (master)
- `docs/superpowers/plans/2026-04-25-aichemy-pricing-{A,B,C,D,E,F}-*.md` (sub-plans)
- `experiments/chem-pricing-verification/VERIFICATION.md` (claim verdicts)

**Vendors actually live in the default chain:**

| Tier | Vendor | Backend | Status |
|---|---|---|---|
| L1 | Fluorochem | direct HTTP (Azure-blob JSON) | live |
| L1 | Molbase | direct HTTP (SSR HTML) | live |
| L2 | MedChemExpress | direct HTTP via curl_cffi (Cloudflare) | live |
| L3a | ChemCruz | Browserbase Fetch | live (needs `BROWSERBASE_API_KEY`) |

**On disk but not in the default chain:**

- **Tocris** (direct-HTTP class) — page restructured; parser keys are gone. Excluded by `_DEFAULT_VENDOR_CLASSES`. Re-add once the parser is rebuilt; see `docs/superpowers/findings/2026-04-26-pubchem-resolver-empirical-findings.md`.
- **Enamine** (Browserbase Browser-API parser) — parser works in isolation, but the L3b tier is disabled in `build_default_chain` because each fall-through cost ~10s of session-setup time. Re-enable once a per-vendor gate short-circuits non-Enamine refs.
- **Cayman / Sigma / Tocris-via-browser** — parsers exist under `aichemy_pricing/browserbase/parsers/` but are not registered in either `parsers/__init__.py` or `browser_parsers/__init__.py`.

**Dropped during verification** (see `experiments/chem-pricing-verification/VERIFICATION.md`): Apollo Scientific (store decommissioned, CLAIM-11), Sigma-Aldrich and TCI (Akamai WAF, deferred), BLDpharm (URL pattern TBD, CLAIM-16), the login-walled tier (Fisher, TRC, Biosynth, Ambeed, etc.), the quote-only tier (AK Scientific, Matrix, BOC, etc.).

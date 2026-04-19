# AIchemy

Profit-maximizing chemo-enzymatic reaction pathway selection via MILP over a unified hypergraph of MetaNetX (enzymatic) and USPTO (chemical) reactions.

See `proposal.md` and `research_reports/` for the scientific motivation and literature review. See `docs/superpowers/specs/` for engineering design docs.

## Status

This repository currently contains the **preprocessing scaffolding**: a working CLI with every pipeline stage stubbed, config system, chemistry primitives, schema validation, and an end-to-end DVC pipeline that runs on empty data. Each preprocessing stage will be implemented in a follow-up plan.

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

### Run the pipeline on stubs

```bash
uv run dvc repro
```

This executes every stage in the DAG and produces empty-but-schema-valid parquet files at `data/processed/`.

### Render the pipeline DAG

```bash
uv run dvc dag
```

### Run tests and lints

```bash
uv run pytest              # tests
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy src/           # typecheck
```

## Project Layout

```
src/aichemy/
├── cli.py                  # Typer entry point
├── config.py               # Pydantic config models + YAML loader
└── preprocessing/
    ├── io.py               # Polars parquet I/O + patito schemas
    ├── pipeline.py         # programmatic API (not the CLI)
    ├── normalize.py        # merge + canonicalize + filter
    ├── sources/            # MetaNetX, USPTO ingestion
    ├── chem/               # SMILES, similarity, filters, identifiers
    ├── dedup/              # molecule + reaction deduplication
    ├── balance/            # SYN-RBL + universal balance validation
    └── augment/            # yields, prices, directionality

configs/
├── default.yaml            # base config — all knobs
└── profiles/               # named overrides (strict_dedup, mean_yields)

tests/
├── unit/                   # pure-function tests
├── integration/            # end-to-end + CLI smoke
└── fixtures/               # sample data (grows as stages are implemented)
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

## Documentation

- `proposal.md` — scientific proposal (MILP formulation, database choices, solver approach)
- `research_reports/` — literature review (SPARROW, ASKCOS, minChemBio, etc.)
- `docs/superpowers/specs/2026-04-19-repo-layout-design.md` — this repo's design spec
- `docs/superpowers/plans/2026-04-19-preprocessing-foundation.md` — implementation plan (this scaffolding)

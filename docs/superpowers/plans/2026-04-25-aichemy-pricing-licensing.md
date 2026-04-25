# Patent Licensing in the AIchemy Pricing MILP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add patent-license cost as a factor in the AIchemy profit-maximization MILP. Three new DVC pipeline stages (PatentsView metadata fetch, CPC-code classification, LLM classification of CPC-ambiguous patents), a merge step that joins license flags onto reactions, two new royalty terms in the MILP objective, and a `solve sweep` CLI for sensitivity analysis over the (process royalty, composition royalty) plane.

**Architecture:** Hybrid CPC heuristic + LLM (eager, persistent JSONL cache) classifies each USPTO patent as process-covered, composition-covered, or both. MetaNetX rows pass through with all flags `False`. The MILP subtracts royalty × revenue terms (linear in existing `f_r` and `q_sell[m]` decision variables — no new binaries). Sensitivity is a separate Typer subcommand that loops `build_and_solve` over a 2-D rate grid and writes a summary parquet with a per-cell `set_hash` for "decision invariance" analysis.

**Tech Stack:** Python 3.11+, Polars, Pydantic, patito, Typer, PuLP, `requests` (PatentsView), `anthropic` SDK (Claude Haiku 4.5), DVC, pytest, `responses` (HTTP mocking in tests).

**Companion spec:** `docs/superpowers/specs/2026-04-25-aichemy-pricing-licensing-design.md` — read this first; it documents the decisions referenced throughout.

---

## File structure

### New files

| Path | Responsibility |
|---|---|
| `config/cpc_rules.yaml` | CPC code → process/composition/ambiguous mapping (data, no logic) |
| `src/aichemy/preprocessing/patents/__init__.py` | Package marker |
| `src/aichemy/preprocessing/patents/fetch.py` | PatentsView REST client; batched fetch with retry; emits `patent_metadata.parquet` |
| `src/aichemy/preprocessing/patents/cpc.py` | Pure function: `(cpc_codes, patent_active, rules) → classification dict`. Loads YAML rules. |
| `src/aichemy/preprocessing/patents/cache.py` | JSONL append-only cache for LLM classifications; keyed by `patent_number` |
| `src/aichemy/preprocessing/patents/llm_classify.py` | Anthropic SDK wrapper; one structured-output call per patent; cache-aware batch |
| `src/aichemy/preprocessing/augment/licenses.py` | Merge step: joins CPC + LLM results onto reactions; emits `reactions_licensed.parquet` |
| `tests/unit/test_patents_fetch.py` | Tests for PatentsView client (HTTP mocked via `responses`) |
| `tests/unit/test_patents_cpc.py` | Tests for CPC classifier rule branches |
| `tests/unit/test_patents_llm_cache.py` | Tests for JSONL cache read/write/idempotency |
| `tests/unit/test_patents_llm_classify.py` | Tests for LLM classifier (Anthropic client stubbed) |
| `tests/unit/test_augment_licenses.py` | Tests for the merge resolution rule |
| `tests/unit/test_solver_royalty.py` | Tests for new MILP objective terms |
| `tests/unit/test_solve_sweep.py` | Tests for the sweep CLI |
| `tests/integration/test_dvc_repro_licenses.py` | End-to-end DVC repro with PatentsView + Anthropic stubbed |
| `tests/fixtures/cpc_rules_test.yaml` | Test-only CPC rules with simplified content |
| `tests/fixtures/patents/sample_patentsview_response.json` | Captured PatentsView response shape for HTTP mocking |

### Modified files

| Path | Change |
|---|---|
| `pyproject.toml` | Add `requests`, `anthropic`, `responses` (test) deps |
| `src/aichemy/config.py` | Add `LicensesConfig` class; wire into `PreprocessingConfig` |
| `src/aichemy/preprocessing/io.py` | Extend `Reaction` patito model + `REACTION_SCHEMA` with 3 new columns; add `patents_path` and `licenses_path` helpers |
| `src/aichemy/cli.py` | New `patents_app` Typer subapp with `fetch`, `classify-cpc`, `classify-llm`; new `augment licenses` subcommand |
| `src/aichemy/solver/config.py` | Add `r_process: float = 0.0`, `r_comp: float = 0.0` |
| `src/aichemy/solver/model.py` | Read 3 new columns; subtract two royalty terms in objective |
| `src/aichemy/solver/cli.py` | Add `sweep` subcommand |
| `dvc.yaml` | Add 4 new stages between `augment_directionality` and `export` |

---

## Tasks

### Task 1: Add Python dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add runtime + test deps**

Edit `pyproject.toml`. Add to `[project.dependencies]` (or `dependencies` array):

```toml
"requests>=2.31",
"anthropic>=0.40.0",
```

Add to dev/test deps section (search for existing `pytest`, add alongside):

```toml
"responses>=0.25",
```

- [ ] **Step 2: Sync the lockfile**

Run: `uv sync`
Expected: completes without errors; `uv.lock` updated.

- [ ] **Step 3: Verify imports work**

Run: `uv run python -c "import requests, anthropic, responses; print('ok')"`
Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat(licensing): add requests, anthropic, responses deps"
```

---

### Task 2: Add CPC rules YAML config

**Files:**
- Create: `config/cpc_rules.yaml`

- [ ] **Step 1: Create the YAML file**

```yaml
# CPC code → license-coverage classification rules.
# Codes are matched as PREFIX (any patent with at least one CPC code that
# starts with one of these strings is a hit). The CPC scheme is hierarchical:
# "C07D 401/12" starts with "C07D", which is a composition code below.

process_codes:
  - "C07B"   # general organic process
  - "C07C"   # acyclic / carbocyclic process
  - "B01J"   # catalysts / reactor processes
  - "C12P"   # fermentation / enzymatic processes
composition_codes:
  - "C07D"   # heterocyclic compounds
  - "C07E"
  - "C07F"
  - "C07G"
  - "C07H"
  - "C07J"
  - "C07K"
ambiguous_codes:
  - "A61K"   # medicinal preparations — composition vs. method-of-use; defer to LLM
```

- [ ] **Step 2: Commit**

```bash
git add config/cpc_rules.yaml
git commit -m "feat(licensing): add CPC rules YAML for license classification"
```

---

### Task 3: Add `LicensesConfig` to `aichemy.config`

**Files:**
- Modify: `src/aichemy/config.py`
- Test: `tests/unit/test_config_licenses.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_config_licenses.py`:

```python
from pathlib import Path
import yaml
import tempfile

from aichemy.config import LicensesConfig, load_config


def test_licenses_config_defaults():
    cfg = LicensesConfig()
    assert cfg.patentsview_endpoint == "https://search.patentsview.org/api/v1/patent"
    assert cfg.llm_model == "claude-haiku-4-5"
    assert cfg.cpc_rules_path == Path("config/cpc_rules.yaml")
    assert cfg.cache_path == Path("data/interim/licenses/llm_cache.jsonl")
    assert cfg.fetch_batch_size == 25
    assert cfg.fetch_max_retries == 3
    assert cfg.llm_max_retries == 3


def test_preprocessing_config_includes_licenses(tmp_path: Path):
    base = tmp_path / "base.yaml"
    base.write_text(yaml.safe_dump({}))
    cfg = load_config(base, [])
    assert cfg.licenses.llm_model == "claude-haiku-4-5"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_config_licenses.py -v`
Expected: FAIL — `ImportError: cannot import name 'LicensesConfig'`.

- [ ] **Step 3: Add `LicensesConfig` to `src/aichemy/config.py`**

Insert after `class YieldConfig(BaseModel):` block (around line 39):

```python
class LicensesConfig(BaseModel):
    model_config = {"extra": "forbid"}

    patentsview_endpoint: str = "https://search.patentsview.org/api/v1/patent"
    cpc_rules_path: Path = Field(default_factory=lambda: Path("config/cpc_rules.yaml"))
    cache_path: Path = Field(
        default_factory=lambda: Path("data/interim/licenses/llm_cache.jsonl")
    )
    llm_model: str = "claude-haiku-4-5"
    fetch_batch_size: int = 25
    fetch_max_retries: int = 3
    llm_max_retries: int = 3
```

Then in `class PreprocessingConfig(BaseModel)` (around line 115), add the field:

```python
licenses: LicensesConfig = Field(default_factory=LicensesConfig)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_config_licenses.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/config.py tests/unit/test_config_licenses.py
git commit -m "feat(licensing): add LicensesConfig to PreprocessingConfig"
```

---

### Task 4: Extend reaction schema with license columns

**Files:**
- Modify: `src/aichemy/preprocessing/io.py`
- Test: `tests/unit/test_io_license_columns.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_io_license_columns.py`:

```python
import polars as pl

from aichemy.preprocessing.io import REACTION_SCHEMA, Reaction


def test_reaction_schema_has_license_columns():
    assert REACTION_SCHEMA["patent_active"] == pl.Boolean
    assert REACTION_SCHEMA["process_covered"] == pl.Boolean
    assert REACTION_SCHEMA["composition_covered"] == pl.Boolean


def test_reaction_model_accepts_license_fields():
    r = Reaction(
        rxn_id="USPTO:7456123:0",
        reaction_smiles="C>>C",
        reactants=[{"mol_id": "M1", "coefficient": 1.0}],
        products=[{"mol_id": "M2", "coefficient": 1.0}],
        type="chemical",
        yield_rate=0.85,
        delta_g=None,
        balanced=True,
        source="uspto",
        patent_active=True,
        process_covered=True,
        composition_covered=False,
    )
    assert r.process_covered is True


def test_reaction_model_license_fields_default_false():
    r = Reaction(
        rxn_id="MNXR1",
        reaction_smiles="C>>C",
        reactants=[],
        products=[],
        type="enzymatic",
        yield_rate=0.85,
        delta_g=None,
        balanced=True,
        source="metanetx",
    )
    assert r.patent_active is False
    assert r.process_covered is False
    assert r.composition_covered is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_io_license_columns.py -v`
Expected: FAIL — `KeyError: 'patent_active'` and validation errors on `Reaction`.

- [ ] **Step 3: Extend `Reaction` patito model**

In `src/aichemy/preprocessing/io.py`, modify the `Reaction` class (lines 26-35):

```python
class Reaction(pt.Model):
    rxn_id: str
    reaction_smiles: str
    reactants: list[Stoichiometry]
    products: list[Stoichiometry]
    type: str  # "enzymatic" | "chemical"
    yield_rate: float
    delta_g: float | None = None
    balanced: bool
    source: str  # "metanetx" | "uspto"
    patent_active: bool = False
    process_covered: bool = False
    composition_covered: bool = False
```

- [ ] **Step 4: Extend `REACTION_SCHEMA`**

In the same file (lines 70-80), add the three keys:

```python
REACTION_SCHEMA = {
    "rxn_id": pl.Utf8,
    "reaction_smiles": pl.Utf8,
    "reactants": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
    "products": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
    "type": pl.Utf8,
    "yield_rate": pl.Float64,
    "delta_g": pl.Float64,
    "balanced": pl.Boolean,
    "source": pl.Utf8,
    "patent_active": pl.Boolean,
    "process_covered": pl.Boolean,
    "composition_covered": pl.Boolean,
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_io_license_columns.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/aichemy/preprocessing/io.py tests/unit/test_io_license_columns.py
git commit -m "feat(licensing): add patent_active/process_covered/composition_covered to Reaction schema"
```

---

### Task 5: Add `patents_path` and `licenses_path` helpers

**Files:**
- Modify: `src/aichemy/preprocessing/io.py`
- Test: `tests/unit/test_io_paths.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_io_paths.py`:

```python
from pathlib import Path

from aichemy.config import PreprocessingConfig
from aichemy.preprocessing.io import licenses_path, patents_path


def test_patents_path():
    cfg = PreprocessingConfig()
    assert patents_path(cfg, "patent_metadata.parquet") == Path(
        "data/interim/patents/patent_metadata.parquet"
    )


def test_licenses_path():
    cfg = PreprocessingConfig()
    assert licenses_path(cfg, "cpc_classifications.parquet") == Path(
        "data/interim/licenses/cpc_classifications.parquet"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_io_paths.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Add the helpers**

Append to `src/aichemy/preprocessing/io.py` (after `processed_path`, around line 55):

```python
def patents_path(config: PreprocessingConfig, *parts: str) -> Path:
    return resolve_data_dir(config).joinpath("interim", "patents", *parts)


def licenses_path(config: PreprocessingConfig, *parts: str) -> Path:
    return resolve_data_dir(config).joinpath("interim", "licenses", *parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_io_paths.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/preprocessing/io.py tests/unit/test_io_paths.py
git commit -m "feat(licensing): add patents_path and licenses_path helpers"
```

---

### Task 6: PatentsView fetch client (pure function)

**Files:**
- Create: `src/aichemy/preprocessing/patents/__init__.py`
- Create: `src/aichemy/preprocessing/patents/fetch.py`
- Test: `tests/unit/test_patents_fetch.py` (create)
- Test: `tests/fixtures/patents/sample_patentsview_response.json` (create)

- [ ] **Step 1: Capture a sample PatentsView response in a fixture**

Create `tests/fixtures/patents/sample_patentsview_response.json`:

```json
{
  "patents": [
    {
      "patent_number": "7456123",
      "patent_date": "2008-11-25",
      "patent_abstract": "A method for the synthesis of substituted heterocyclic compounds...",
      "claims": [{"text": "1. A process for preparing a compound of formula I..."}],
      "cpcs": [
        {"cpc_group_id": "C07D 401/12"},
        {"cpc_group_id": "A61K 31/505"}
      ],
      "assignees": [{"assignee_organization": "Acme Pharmaceuticals"}],
      "application": {"filing_date": "2005-03-14"}
    },
    {
      "patent_number": "9999999",
      "patent_date": null,
      "patent_abstract": null,
      "claims": [],
      "cpcs": [],
      "assignees": [],
      "application": {"filing_date": "1985-01-01"}
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_patents_fetch.py`:

```python
import json
from pathlib import Path

import responses

from aichemy.preprocessing.patents.fetch import (
    PatentMetadata,
    fetch_patents,
)


FIXTURE = Path(__file__).parent.parent / "fixtures" / "patents" / "sample_patentsview_response.json"
ENDPOINT = "https://search.patentsview.org/api/v1/patent"


@responses.activate
def test_fetch_patents_returns_metadata_objects():
    responses.add(
        responses.POST,
        ENDPOINT,
        json=json.loads(FIXTURE.read_text()),
        status=200,
    )
    out = fetch_patents(["7456123", "9999999"], endpoint=ENDPOINT, max_retries=1)
    assert len(out) == 2
    by_id = {p.patent_number: p for p in out}
    assert by_id["7456123"].filing_date == "2005-03-14"
    assert by_id["7456123"].abstract.startswith("A method")
    assert "C07D 401/12" in by_id["7456123"].cpc_codes
    assert by_id["7456123"].claims_text.startswith("1. A process")
    assert by_id["7456123"].fetch_status == "ok"
    assert by_id["9999999"].abstract is None
    assert by_id["9999999"].fetch_status == "ok"


@responses.activate
def test_fetch_patents_records_error_status_after_retry_exhaustion():
    responses.add(responses.POST, ENDPOINT, status=500)
    out = fetch_patents(["7456123"], endpoint=ENDPOINT, max_retries=2)
    assert len(out) == 1
    assert out[0].fetch_status == "error"


def test_patent_metadata_dataclass_shape():
    p = PatentMetadata(
        patent_number="123",
        filing_date="2010-01-01",
        grant_date=None,
        abstract=None,
        claims_text=None,
        cpc_codes=[],
        assignee=None,
        fetch_status="ok",
    )
    assert p.patent_number == "123"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_patents_fetch.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Create the package marker**

Create `src/aichemy/preprocessing/patents/__init__.py`:

```python
"""Patent metadata fetching and license classification."""
```

- [ ] **Step 5: Implement the fetch client**

Create `src/aichemy/preprocessing/patents/fetch.py`:

```python
"""PatentsView REST client.

Fetches patent metadata (filing date, abstract, claims, CPC codes) for the
USPTO patent numbers extracted from reaction `rxn_id`s. Used by the
`fetch_patent_metadata` DVC stage.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)


@dataclass
class PatentMetadata:
    patent_number: str
    filing_date: str | None
    grant_date: str | None
    abstract: str | None
    claims_text: str | None
    cpc_codes: list[str]
    assignee: str | None
    fetch_status: str  # "ok" | "not_found" | "error"


def fetch_patents(
    patent_numbers: list[str],
    *,
    endpoint: str,
    max_retries: int = 3,
    batch_size: int = 25,
    backoff_seconds: float = 1.0,
) -> list[PatentMetadata]:
    """Fetch metadata for the given patent numbers.

    PatentsView accepts a JSON POST with a query in its query DSL. We batch
    requests to amortize round-trip cost, retry on transient errors, and
    record `fetch_status="error"` on permanent failure (rather than raise,
    so the pipeline doesn't crash).
    """
    out: list[PatentMetadata] = []
    seen: set[str] = set()
    for i in range(0, len(patent_numbers), batch_size):
        batch = patent_numbers[i : i + batch_size]
        results = _fetch_batch(batch, endpoint, max_retries, backoff_seconds)
        for r in results:
            seen.add(r.patent_number)
            out.append(r)
    # Any patent we never got back is recorded as error (rare).
    for pn in patent_numbers:
        if pn not in seen:
            out.append(_error_record(pn))
    return out


def _fetch_batch(
    batch: list[str],
    endpoint: str,
    max_retries: int,
    backoff_seconds: float,
) -> list[PatentMetadata]:
    payload = {
        "q": {"patent_number": batch},
        "f": [
            "patent_number",
            "patent_date",
            "patent_abstract",
            "claims",
            "cpcs",
            "assignees",
            "application",
        ],
        "o": {"per_page": len(batch)},
    }
    for attempt in range(max_retries):
        try:
            r = requests.post(endpoint, json=payload, timeout=30)
            if r.status_code == 200:
                return _parse_response(r.json(), batch)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2**attempt))
                continue
            log.warning("PatentsView returned %s for batch=%s", r.status_code, batch[:3])
            break
        except requests.RequestException as exc:
            log.warning("PatentsView request failed (attempt %d): %s", attempt + 1, exc)
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2**attempt))
                continue
    return [_error_record(pn) for pn in batch]


def _parse_response(body: dict, batch: list[str]) -> list[PatentMetadata]:
    by_id: dict[str, PatentMetadata] = {}
    for p in body.get("patents") or []:
        pn = str(p.get("patent_number"))
        claims_text = " ".join(c.get("text", "") for c in (p.get("claims") or []))
        cpc_codes = [c.get("cpc_group_id", "") for c in (p.get("cpcs") or [])]
        cpc_codes = [c for c in cpc_codes if c]
        assignees = p.get("assignees") or []
        assignee = assignees[0].get("assignee_organization") if assignees else None
        application = p.get("application") or {}
        by_id[pn] = PatentMetadata(
            patent_number=pn,
            filing_date=application.get("filing_date"),
            grant_date=p.get("patent_date"),
            abstract=p.get("patent_abstract"),
            claims_text=claims_text or None,
            cpc_codes=cpc_codes,
            assignee=assignee,
            fetch_status="ok",
        )
    out: list[PatentMetadata] = []
    for pn in batch:
        if pn in by_id:
            out.append(by_id[pn])
        else:
            out.append(
                PatentMetadata(
                    patent_number=pn,
                    filing_date=None,
                    grant_date=None,
                    abstract=None,
                    claims_text=None,
                    cpc_codes=[],
                    assignee=None,
                    fetch_status="not_found",
                )
            )
    return out


def _error_record(patent_number: str) -> PatentMetadata:
    return PatentMetadata(
        patent_number=patent_number,
        filing_date=None,
        grant_date=None,
        abstract=None,
        claims_text=None,
        cpc_codes=[],
        assignee=None,
        fetch_status="error",
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_patents_fetch.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add src/aichemy/preprocessing/patents/__init__.py \
        src/aichemy/preprocessing/patents/fetch.py \
        tests/unit/test_patents_fetch.py \
        tests/fixtures/patents/sample_patentsview_response.json
git commit -m "feat(licensing): add PatentsView REST client with retry"
```

---

### Task 7: `aichemy patents fetch` CLI subcommand

**Files:**
- Modify: `src/aichemy/cli.py`
- Modify: `src/aichemy/preprocessing/patents/fetch.py` (add `write_metadata_parquet`)
- Test: `tests/unit/test_patents_fetch.py` (extend)

- [ ] **Step 1: Write the failing test for parquet writer**

Append to `tests/unit/test_patents_fetch.py`:

```python
import polars as pl

from aichemy.preprocessing.patents.fetch import write_metadata_parquet


def test_write_metadata_parquet(tmp_path: Path):
    items = [
        PatentMetadata(
            patent_number="123",
            filing_date="2010-01-01",
            grant_date="2012-06-15",
            abstract="abc",
            claims_text="1. claim",
            cpc_codes=["C07D"],
            assignee="X Inc",
            fetch_status="ok",
        ),
    ]
    out = tmp_path / "patents.parquet"
    write_metadata_parquet(items, out)
    df = pl.read_parquet(out)
    assert df.height == 1
    assert df["patent_number"][0] == "123"
    assert df["cpc_codes"][0].to_list() == ["C07D"]
    assert df["fetch_status"][0] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_patents_fetch.py::test_write_metadata_parquet -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Add the parquet writer to fetch.py**

Append to `src/aichemy/preprocessing/patents/fetch.py`:

```python
from pathlib import Path

import polars as pl


PATENT_METADATA_SCHEMA = {
    "patent_number": pl.Utf8,
    "filing_date": pl.Utf8,
    "grant_date": pl.Utf8,
    "abstract": pl.Utf8,
    "claims_text": pl.Utf8,
    "cpc_codes": pl.List(pl.Utf8),
    "assignee": pl.Utf8,
    "fetch_status": pl.Utf8,
}


def write_metadata_parquet(items: list[PatentMetadata], path: Path) -> None:
    rows = [
        {
            "patent_number": p.patent_number,
            "filing_date": p.filing_date,
            "grant_date": p.grant_date,
            "abstract": p.abstract,
            "claims_text": p.claims_text,
            "cpc_codes": p.cpc_codes,
            "assignee": p.assignee,
            "fetch_status": p.fetch_status,
        }
        for p in items
    ]
    df = pl.DataFrame(rows, schema=PATENT_METADATA_SCHEMA)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
```

(Move the `from pathlib import Path` and `import polars as pl` to the top of the file with the other imports.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_patents_fetch.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Add `patents_app` Typer subapp and `fetch` subcommand to cli.py**

In `src/aichemy/cli.py`, after the existing `augment_app` line:

```python
patents_app = typer.Typer(help="Patent metadata fetching and license classification.")
app.add_typer(patents_app, name="patents")
```

Then add the subcommand (place near the other augment subcommands):

```python
@patents_app.command("fetch")
def patents_fetch(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Fetch PatentsView metadata for every USPTO patent referenced by reactions."""
    from aichemy.preprocessing.io import (
        interim_path,
        patents_path,
        read_reactions,
    )
    from aichemy.preprocessing.patents.fetch import (
        fetch_patents,
        write_metadata_parquet,
    )

    cfg = _load(config, override)
    reactions = read_reactions(interim_path(cfg, "augmented", "reactions_full.parquet"))

    uspto_rxns = reactions.filter(pl.col("source") == "uspto")
    patent_numbers = sorted({rid.split(":")[1] for rid in uspto_rxns["rxn_id"].to_list()})
    typer.echo(f"[patents fetch] {len(patent_numbers)} unique USPTO patents to fetch")

    items = fetch_patents(
        patent_numbers,
        endpoint=cfg.licenses.patentsview_endpoint,
        max_retries=cfg.licenses.fetch_max_retries,
        batch_size=cfg.licenses.fetch_batch_size,
    )
    out_path = patents_path(cfg, "patent_metadata.parquet")
    write_metadata_parquet(items, out_path)

    n_ok = sum(1 for p in items if p.fetch_status == "ok")
    typer.echo(
        f"[patents fetch] wrote {len(items)} rows ({n_ok} ok) → {out_path}"
    )
```

- [ ] **Step 6: Verify CLI registers**

Run: `uv run aichemy patents --help`
Expected: prints help that includes `fetch`.

- [ ] **Step 7: Commit**

```bash
git add src/aichemy/cli.py \
        src/aichemy/preprocessing/patents/fetch.py \
        tests/unit/test_patents_fetch.py
git commit -m "feat(licensing): add 'aichemy patents fetch' CLI subcommand"
```

---

### Task 8: CPC classifier (pure function)

**Files:**
- Create: `src/aichemy/preprocessing/patents/cpc.py`
- Create: `tests/fixtures/cpc_rules_test.yaml`
- Test: `tests/unit/test_patents_cpc.py` (create)

- [ ] **Step 1: Create the test fixture**

Create `tests/fixtures/cpc_rules_test.yaml`:

```yaml
process_codes:
  - "C07B"
  - "C07C"
composition_codes:
  - "C07D"
  - "C07K"
ambiguous_codes:
  - "A61K"
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_patents_cpc.py`:

```python
from datetime import date
from pathlib import Path

from aichemy.preprocessing.patents.cpc import (
    CPCRules,
    classify_patent,
    load_cpc_rules,
)


RULES_PATH = Path(__file__).parent.parent / "fixtures" / "cpc_rules_test.yaml"


def _rules() -> CPCRules:
    return load_cpc_rules(RULES_PATH)


def test_inactive_patent_short_circuits():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07D 401/12"],
        filing_date_str="1985-01-01",
        today=today,
        rules=_rules(),
    )
    assert out.patent_active is False
    assert out.process_covered_cpc is False
    assert out.composition_covered_cpc is False
    assert out.cpc_ambiguous is False


def test_active_process_only():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07C 1/00"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.patent_active is True
    assert out.cpc_process_hit is True
    assert out.cpc_composition_hit is False
    assert out.cpc_ambiguous is False
    assert out.process_covered_cpc is True
    assert out.composition_covered_cpc is False


def test_active_composition_only():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07D 401/12"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.cpc_process_hit is False
    assert out.cpc_composition_hit is True
    assert out.cpc_ambiguous is False
    assert out.process_covered_cpc is False
    assert out.composition_covered_cpc is True


def test_active_both_hit_is_ambiguous():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07C 1/00", "C07D 401/12"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.cpc_ambiguous is True
    assert out.process_covered_cpc is False
    assert out.composition_covered_cpc is False


def test_active_a61k_is_ambiguous():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["A61K 31/505"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.cpc_ambiguous is True


def test_active_no_chemistry_codes_is_ambiguous():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["G06F 17/00"],
        filing_date_str="2015-06-01",
        today=today,
        rules=_rules(),
    )
    assert out.cpc_ambiguous is True


def test_missing_filing_date_treated_inactive():
    today = date(2026, 4, 25)
    out = classify_patent(
        cpc_codes=["C07D"],
        filing_date_str=None,
        today=today,
        rules=_rules(),
    )
    assert out.patent_active is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_patents_cpc.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 4: Implement the classifier**

Create `src/aichemy/preprocessing/patents/cpc.py`:

```python
"""CPC-code classifier for patent licensing.

Pure function operating on a single patent's CPC codes + filing date,
producing booleans that downstream stages consume. Rules are loaded from
a YAML config so they can be tweaked without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

PATENT_TERM_YEARS = 20


@dataclass
class CPCRules:
    process_codes: list[str]
    composition_codes: list[str]
    ambiguous_codes: list[str]


@dataclass
class CPCClassification:
    patent_active: bool
    cpc_process_hit: bool
    cpc_composition_hit: bool
    cpc_ambiguous: bool
    process_covered_cpc: bool
    composition_covered_cpc: bool


def load_cpc_rules(path: Path) -> CPCRules:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return CPCRules(
        process_codes=list(raw.get("process_codes") or []),
        composition_codes=list(raw.get("composition_codes") or []),
        ambiguous_codes=list(raw.get("ambiguous_codes") or []),
    )


def classify_patent(
    *,
    cpc_codes: list[str],
    filing_date_str: str | None,
    today: date,
    rules: CPCRules,
) -> CPCClassification:
    """Classify one patent. Inactive patents short-circuit to all-False."""
    patent_active = _is_active(filing_date_str, today)
    if not patent_active:
        return CPCClassification(
            patent_active=False,
            cpc_process_hit=False,
            cpc_composition_hit=False,
            cpc_ambiguous=False,
            process_covered_cpc=False,
            composition_covered_cpc=False,
        )

    process_hit = _any_prefix_match(cpc_codes, rules.process_codes)
    composition_hit = _any_prefix_match(cpc_codes, rules.composition_codes)
    ambiguous_explicit = _any_prefix_match(cpc_codes, rules.ambiguous_codes)
    has_any_chemistry = process_hit or composition_hit or ambiguous_explicit

    ambiguous = (
        ambiguous_explicit
        or (process_hit and composition_hit)
        or not has_any_chemistry
    )

    return CPCClassification(
        patent_active=True,
        cpc_process_hit=process_hit,
        cpc_composition_hit=composition_hit,
        cpc_ambiguous=ambiguous,
        process_covered_cpc=process_hit and not ambiguous,
        composition_covered_cpc=composition_hit and not ambiguous,
    )


def _any_prefix_match(codes: list[str], prefixes: list[str]) -> bool:
    return any(c.startswith(p) for c in codes for p in prefixes)


def _is_active(filing_date_str: str | None, today: date) -> bool:
    if not filing_date_str:
        return False
    try:
        filed = date.fromisoformat(filing_date_str)
    except ValueError:
        return False
    expiry = date(filed.year + PATENT_TERM_YEARS, filed.month, filed.day)
    return today < expiry
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_patents_cpc.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add src/aichemy/preprocessing/patents/cpc.py \
        tests/fixtures/cpc_rules_test.yaml \
        tests/unit/test_patents_cpc.py
git commit -m "feat(licensing): add CPC-code classifier"
```

---

### Task 9: `aichemy patents classify-cpc` CLI subcommand

**Files:**
- Modify: `src/aichemy/preprocessing/patents/cpc.py` (add `classify_dataframe` + parquet writer)
- Modify: `src/aichemy/cli.py`
- Test: `tests/unit/test_patents_cpc.py` (extend)

- [ ] **Step 1: Write the failing test for the dataframe-level function**

Append to `tests/unit/test_patents_cpc.py`:

```python
import polars as pl

from aichemy.preprocessing.patents.cpc import classify_dataframe, CPC_CLASSIFICATION_SCHEMA


def test_classify_dataframe_joins_reactions_and_patents():
    today = date(2026, 4, 25)
    rules = _rules()
    reactions = pl.DataFrame(
        {
            "rxn_id": ["USPTO:7456123:0", "USPTO:1985111:0", "MNXR1"],
            "source": ["uspto", "uspto", "metanetx"],
        }
    )
    patents = pl.DataFrame(
        {
            "patent_number": ["7456123", "1985111"],
            "filing_date": ["2015-06-01", "1985-01-01"],
            "cpc_codes": [["C07D 401/12"], ["C07D 401/12"]],
        }
    )
    out = classify_dataframe(reactions, patents, rules=rules, today=today)
    # Only USPTO rows present (MetaNetX excluded — no patent association)
    assert out.height == 2
    by_rxn = {r["rxn_id"]: r for r in out.iter_rows(named=True)}
    assert by_rxn["USPTO:7456123:0"]["patent_active"] is True
    assert by_rxn["USPTO:7456123:0"]["composition_covered_cpc"] is True
    assert by_rxn["USPTO:1985111:0"]["patent_active"] is False
    # Schema check
    for col, dtype in CPC_CLASSIFICATION_SCHEMA.items():
        assert col in out.columns
        assert out.schema[col] == dtype
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_patents_cpc.py::test_classify_dataframe_joins_reactions_and_patents -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement `classify_dataframe`**

Append to `src/aichemy/preprocessing/patents/cpc.py`:

```python
import polars as pl


CPC_CLASSIFICATION_SCHEMA = {
    "rxn_id": pl.Utf8,
    "patent_number": pl.Utf8,
    "patent_active": pl.Boolean,
    "cpc_process_hit": pl.Boolean,
    "cpc_composition_hit": pl.Boolean,
    "cpc_ambiguous": pl.Boolean,
    "process_covered_cpc": pl.Boolean,
    "composition_covered_cpc": pl.Boolean,
}


def classify_dataframe(
    reactions: pl.DataFrame,
    patents: pl.DataFrame,
    *,
    rules: CPCRules,
    today: date,
) -> pl.DataFrame:
    """Produce one row per (rxn_id, patent_number) for USPTO reactions."""
    uspto = reactions.filter(pl.col("source") == "uspto")
    rxn_rows = []
    for rid in uspto["rxn_id"].to_list():
        parts = rid.split(":")
        if len(parts) >= 3 and parts[0] == "USPTO":
            rxn_rows.append({"rxn_id": rid, "patent_number": parts[1]})
    rxn_df = pl.DataFrame(rxn_rows, schema={"rxn_id": pl.Utf8, "patent_number": pl.Utf8})

    joined = rxn_df.join(patents, on="patent_number", how="left")

    out_rows: list[dict] = []
    for r in joined.iter_rows(named=True):
        cpc_codes = list(r.get("cpc_codes") or [])
        c = classify_patent(
            cpc_codes=cpc_codes,
            filing_date_str=r.get("filing_date"),
            today=today,
            rules=rules,
        )
        out_rows.append(
            {
                "rxn_id": r["rxn_id"],
                "patent_number": r["patent_number"],
                "patent_active": c.patent_active,
                "cpc_process_hit": c.cpc_process_hit,
                "cpc_composition_hit": c.cpc_composition_hit,
                "cpc_ambiguous": c.cpc_ambiguous,
                "process_covered_cpc": c.process_covered_cpc,
                "composition_covered_cpc": c.composition_covered_cpc,
            }
        )
    return pl.DataFrame(out_rows, schema=CPC_CLASSIFICATION_SCHEMA)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_patents_cpc.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Add the CLI subcommand**

In `src/aichemy/cli.py`, add after the `patents_fetch` command:

```python
@patents_app.command("classify-cpc")
def patents_classify_cpc(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Classify each (rxn_id, patent) pair via CPC-code rules."""
    from datetime import date

    from aichemy.preprocessing.io import (
        interim_path,
        licenses_path,
        patents_path,
        read_reactions,
    )
    from aichemy.preprocessing.patents.cpc import (
        classify_dataframe,
        load_cpc_rules,
    )

    cfg = _load(config, override)
    reactions = read_reactions(interim_path(cfg, "augmented", "reactions_full.parquet"))
    patents = pl.read_parquet(patents_path(cfg, "patent_metadata.parquet"))
    rules = load_cpc_rules(cfg.licenses.cpc_rules_path)

    out = classify_dataframe(reactions, patents, rules=rules, today=date.today())
    out_path = licenses_path(cfg, "cpc_classifications.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.write_parquet(out_path)

    n_ambig = int(out["cpc_ambiguous"].sum())
    n_active = int(out["patent_active"].sum())
    typer.echo(
        f"[patents classify-cpc] {out.height} rows "
        f"({n_active} active, {n_ambig} ambiguous → LLM) → {out_path}"
    )
```

- [ ] **Step 6: Verify CLI registers**

Run: `uv run aichemy patents classify-cpc --help`
Expected: prints help.

- [ ] **Step 7: Commit**

```bash
git add src/aichemy/preprocessing/patents/cpc.py \
        src/aichemy/cli.py \
        tests/unit/test_patents_cpc.py
git commit -m "feat(licensing): add 'aichemy patents classify-cpc' CLI subcommand"
```

---

### Task 10: LLM JSONL cache

**Files:**
- Create: `src/aichemy/preprocessing/patents/cache.py`
- Test: `tests/unit/test_patents_llm_cache.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_patents_llm_cache.py`:

```python
from pathlib import Path

from aichemy.preprocessing.patents.cache import (
    LLMCacheEntry,
    append_cache,
    load_cache,
)


def test_load_cache_missing_file_returns_empty(tmp_path: Path):
    cache_path = tmp_path / "cache.jsonl"
    assert load_cache(cache_path) == {}


def test_append_then_load_roundtrip(tmp_path: Path):
    cache_path = tmp_path / "cache.jsonl"
    e = LLMCacheEntry(
        patent_number="123",
        process_covered=True,
        composition_covered=False,
        confidence=0.9,
        rationale="claim 1 covers a method",
        model="claude-haiku-4-5",
        ts="2026-04-25T00:00:00Z",
    )
    append_cache(cache_path, e)
    loaded = load_cache(cache_path)
    assert "123" in loaded
    assert loaded["123"].process_covered is True


def test_later_entry_wins_for_duplicate_keys(tmp_path: Path):
    cache_path = tmp_path / "cache.jsonl"
    e1 = LLMCacheEntry(
        patent_number="X",
        process_covered=False,
        composition_covered=False,
        confidence=0.5,
        rationale="r1",
        model="m1",
        ts="2026-01-01T00:00:00Z",
    )
    e2 = LLMCacheEntry(
        patent_number="X",
        process_covered=True,
        composition_covered=True,
        confidence=0.9,
        rationale="r2",
        model="m1",
        ts="2026-04-01T00:00:00Z",
    )
    append_cache(cache_path, e1)
    append_cache(cache_path, e2)
    loaded = load_cache(cache_path)
    assert loaded["X"].process_covered is True
    assert loaded["X"].rationale == "r2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_patents_llm_cache.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the cache**

Create `src/aichemy/preprocessing/patents/cache.py`:

```python
"""JSONL append-only cache for LLM patent classifications.

One entry per LLM call. Cache key is `patent_number`. PatentsView is
canonical (abstract/claims for a given patent_number are stable), so the
cache hit on `patent_number` alone is correct.

Append-only design means the file is human-readable, easy to inspect, and
each invocation extends the file rather than rewriting it. On read, later
entries with the same `patent_number` win.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class LLMCacheEntry:
    patent_number: str
    process_covered: bool
    composition_covered: bool
    confidence: float
    rationale: str
    model: str
    ts: str


def load_cache(path: Path) -> dict[str, LLMCacheEntry]:
    """Read cache; later entries with the same patent_number win."""
    if not path.exists():
        return {}
    out: dict[str, LLMCacheEntry] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            out[data["patent_number"]] = LLMCacheEntry(**data)
    return out


def append_cache(path: Path, entry: LLMCacheEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(asdict(entry)) + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_patents_llm_cache.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/preprocessing/patents/cache.py \
        tests/unit/test_patents_llm_cache.py
git commit -m "feat(licensing): add JSONL cache for LLM classifications"
```

---

### Task 11: LLM single-classify call (Anthropic SDK, mocked)

**Files:**
- Create: `src/aichemy/preprocessing/patents/llm_classify.py`
- Test: `tests/unit/test_patents_llm_classify.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_patents_llm_classify.py`:

```python
from unittest.mock import MagicMock

from aichemy.preprocessing.patents.llm_classify import (
    LLMClassificationResult,
    classify_patent_llm,
)


def _stub_anthropic_response(*, process: bool, composition: bool, confidence: float, rationale: str):
    """Build a mock that mimics anthropic.Anthropic().messages.create() returning tool-use."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = "report_classification"
    block.input = {
        "process_covered": process,
        "composition_covered": composition,
        "confidence": confidence,
        "rationale": rationale,
    }
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.content = [block]
    return msg


def test_classify_patent_llm_parses_tool_use():
    client = MagicMock()
    client.messages.create.return_value = _stub_anthropic_response(
        process=True, composition=False, confidence=0.86, rationale="claim 1 method",
    )
    out = classify_patent_llm(
        client=client,
        patent_number="7456123",
        title="A method",
        abstract="Method for synthesis…",
        claims_text="1. A process for…",
        reaction_smiles_examples=["A>>B"],
        model="claude-haiku-4-5",
    )
    assert isinstance(out, LLMClassificationResult)
    assert out.process_covered is True
    assert out.composition_covered is False
    assert out.confidence == 0.86
    assert out.rationale.startswith("claim")


def test_classify_patent_llm_returns_none_on_unexpected_stop_reason():
    client = MagicMock()
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = []
    client.messages.create.return_value = msg
    out = classify_patent_llm(
        client=client,
        patent_number="X",
        title="t", abstract="a", claims_text="c", reaction_smiles_examples=[],
        model="claude-haiku-4-5",
    )
    assert out is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_patents_llm_classify.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement single-call classifier**

Create `src/aichemy/preprocessing/patents/llm_classify.py`:

```python
"""LLM patent classifier using the Anthropic SDK with structured tool-use.

The model is asked to judge two booleans (process_covered, composition_covered)
plus a self-reported confidence and one-sentence rationale. We use Claude's
tool-use schema to enforce structure rather than free-form JSON parsing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


CLASSIFICATION_TOOL = {
    "name": "report_classification",
    "description": (
        "Report whether the given patent's claims cover the synthesis route "
        "(process) and/or any compound that participates in the reaction "
        "(composition-of-matter)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "process_covered": {
                "type": "boolean",
                "description": (
                    "True iff the patent's INDEPENDENT claims cover this specific "
                    "synthesis route (using these reactants, these conditions, this "
                    "transformation). Mere disclosure in examples or background does NOT count."
                ),
            },
            "composition_covered": {
                "type": "boolean",
                "description": (
                    "True iff the patent's INDEPENDENT claims cover any participant "
                    "compound (reactant, intermediate, or product) by composition-of-matter."
                ),
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Self-reported confidence in this classification.",
            },
            "rationale": {
                "type": "string",
                "description": "One sentence citing the specific claim/passage that supports the answer.",
            },
        },
        "required": ["process_covered", "composition_covered", "confidence", "rationale"],
    },
}


SYSTEM_PROMPT = (
    "You are a patent-claims analyst. Given a USPTO patent's title, abstract, and "
    "independent claims, plus example reaction SMILES extracted from the patent, decide "
    "whether the patent's CLAIMS (not its background or examples) cover the reaction's "
    "synthesis route (process) and/or any participant compound by composition-of-matter. "
    "Be strict: only report True when the claims clearly cover the item. When in doubt, "
    "report False with a low confidence."
)


@dataclass
class LLMClassificationResult:
    process_covered: bool
    composition_covered: bool
    confidence: float
    rationale: str


def classify_patent_llm(
    *,
    client: Any,
    patent_number: str,
    title: str | None,
    abstract: str | None,
    claims_text: str | None,
    reaction_smiles_examples: list[str],
    model: str,
) -> LLMClassificationResult | None:
    """One LLM call, one classification. Returns None on unexpected stop_reason."""
    examples = "\n".join(reaction_smiles_examples[:5]) or "(none)"
    user = (
        f"Patent number: {patent_number}\n\n"
        f"Title: {title or '(none)'}\n\n"
        f"Abstract:\n{abstract or '(none)'}\n\n"
        f"Independent claims:\n{(claims_text or '(none)')[:8000]}\n\n"
        f"Reaction SMILES extracted from this patent:\n{examples}\n\n"
        "Use the report_classification tool."
    )
    msg = client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=[CLASSIFICATION_TOOL],
        tool_choice={"type": "tool", "name": "report_classification"},
        messages=[{"role": "user", "content": user}],
    )
    if msg.stop_reason != "tool_use":
        log.warning(
            "Unexpected stop_reason=%s for patent=%s", msg.stop_reason, patent_number
        )
        return None
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "report_classification":
            data = block.input
            return LLMClassificationResult(
                process_covered=bool(data["process_covered"]),
                composition_covered=bool(data["composition_covered"]),
                confidence=float(data["confidence"]),
                rationale=str(data["rationale"]),
            )
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_patents_llm_classify.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/preprocessing/patents/llm_classify.py \
        tests/unit/test_patents_llm_classify.py
git commit -m "feat(licensing): add LLM single-call patent classifier"
```

---

### Task 12: LLM batch classifier with cache + retry + parquet output

**Files:**
- Modify: `src/aichemy/preprocessing/patents/llm_classify.py`
- Test: `tests/unit/test_patents_llm_classify.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_patents_llm_classify.py`:

```python
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, call

import polars as pl

from aichemy.preprocessing.patents.cache import LLMCacheEntry, append_cache
from aichemy.preprocessing.patents.llm_classify import (
    LLM_CLASSIFICATION_SCHEMA,
    classify_ambiguous_patents,
)


def test_classify_ambiguous_patents_uses_cache_when_present(tmp_path: Path):
    cache_path = tmp_path / "cache.jsonl"
    append_cache(
        cache_path,
        LLMCacheEntry(
            patent_number="A",
            process_covered=True,
            composition_covered=False,
            confidence=0.9,
            rationale="cached",
            model="claude-haiku-4-5",
            ts=datetime.now(tz=timezone.utc).isoformat(),
        ),
    )
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:A:0"],
            "patent_number": ["A"],
            "patent_active": [True],
            "cpc_ambiguous": [True],
        }
    )
    patents = pl.DataFrame(
        {
            "patent_number": ["A"],
            "abstract": ["x"],
            "claims_text": ["1. claim"],
            "cpc_codes": [["A61K"]],
        }
    )
    reactions = pl.DataFrame({"rxn_id": ["USPTO:A:0"], "reaction_smiles": ["A>>B"]})
    client = MagicMock()
    out_path = tmp_path / "llm.parquet"
    out_df = classify_ambiguous_patents(
        cpc=cpc,
        patents=patents,
        reactions=reactions,
        cache_path=cache_path,
        out_path=out_path,
        client=client,
        model="claude-haiku-4-5",
        max_retries=1,
    )
    assert client.messages.create.call_count == 0  # cache hit
    assert out_df.height == 1
    assert out_df["cache_hit"][0] is True
    assert out_df["process_covered"][0] is True
    for col, dtype in LLM_CLASSIFICATION_SCHEMA.items():
        assert col in out_df.columns
        assert out_df.schema[col] == dtype


def test_classify_ambiguous_patents_calls_llm_on_cache_miss(tmp_path: Path):
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:B:0"],
            "patent_number": ["B"],
            "patent_active": [True],
            "cpc_ambiguous": [True],
        }
    )
    patents = pl.DataFrame(
        {
            "patent_number": ["B"],
            "abstract": ["xyz"],
            "claims_text": ["1. claim"],
            "cpc_codes": [["A61K"]],
        }
    )
    reactions = pl.DataFrame({"rxn_id": ["USPTO:B:0"], "reaction_smiles": ["A>>B"]})
    client = MagicMock()
    client.messages.create.return_value = _stub_anthropic_response(
        process=False, composition=True, confidence=0.7, rationale="composition only",
    )
    cache_path = tmp_path / "cache.jsonl"
    out_path = tmp_path / "llm.parquet"
    out_df = classify_ambiguous_patents(
        cpc=cpc, patents=patents, reactions=reactions,
        cache_path=cache_path, out_path=out_path,
        client=client, model="claude-haiku-4-5", max_retries=1,
    )
    assert client.messages.create.call_count == 1
    assert out_df["cache_hit"][0] is False
    assert out_df["composition_covered"][0] is True
    # Cache file now has one entry
    assert cache_path.exists()
    assert "B" in cache_path.read_text()


def test_classify_ambiguous_patents_skips_inactive(tmp_path: Path):
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:C:0"],
            "patent_number": ["C"],
            "patent_active": [False],
            "cpc_ambiguous": [True],
        }
    )
    patents = pl.DataFrame(
        {"patent_number": ["C"], "abstract": [None], "claims_text": [None], "cpc_codes": [[]]}
    )
    reactions = pl.DataFrame({"rxn_id": ["USPTO:C:0"], "reaction_smiles": ["A>>B"]})
    client = MagicMock()
    out_path = tmp_path / "llm.parquet"
    out_df = classify_ambiguous_patents(
        cpc=cpc, patents=patents, reactions=reactions,
        cache_path=tmp_path / "cache.jsonl", out_path=out_path,
        client=client, model="claude-haiku-4-5", max_retries=1,
    )
    # Inactive patents are not LLM-classified
    assert out_df.height == 0
    assert client.messages.create.call_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_patents_llm_classify.py -v`
Expected: FAIL — `ImportError` on `classify_ambiguous_patents`.

- [ ] **Step 3: Implement batch classifier**

Append to `src/aichemy/preprocessing/patents/llm_classify.py`:

```python
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from aichemy.preprocessing.patents.cache import LLMCacheEntry, append_cache, load_cache


LLM_CLASSIFICATION_SCHEMA = {
    "patent_number": pl.Utf8,
    "process_covered": pl.Boolean,
    "composition_covered": pl.Boolean,
    "confidence": pl.Float64,
    "rationale": pl.Utf8,
    "model": pl.Utf8,
    "cache_hit": pl.Boolean,
}


def classify_ambiguous_patents(
    *,
    cpc: pl.DataFrame,
    patents: pl.DataFrame,
    reactions: pl.DataFrame,
    cache_path: Path,
    out_path: Path,
    client: Any,
    model: str,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
) -> pl.DataFrame:
    """Classify each unique patent flagged ambiguous + active.

    Cache hits don't call the LLM. Misses call once per patent (no retries
    on the LLM logic itself; transport-level retries on connection errors).
    Failed calls fall back to (False, False, 0.0) and are NOT cached.
    """
    target_patents = (
        cpc.filter(pl.col("cpc_ambiguous") & pl.col("patent_active"))
        .select("patent_number")
        .unique()
        ["patent_number"]
        .to_list()
    )

    cache = load_cache(cache_path)
    rxn_smiles_by_patent = _smiles_index(cpc, reactions)
    patent_meta = {
        r["patent_number"]: r for r in patents.iter_rows(named=True)
    }

    rows: list[dict] = []
    for pn in target_patents:
        if pn in cache:
            entry = cache[pn]
            rows.append(_to_row(entry, cache_hit=True))
            continue

        meta = patent_meta.get(pn, {})
        result = _call_with_retry(
            client=client,
            model=model,
            patent_number=pn,
            abstract=meta.get("abstract"),
            claims_text=meta.get("claims_text"),
            smiles_examples=rxn_smiles_by_patent.get(pn, []),
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
        if result is None:
            rows.append(
                {
                    "patent_number": pn,
                    "process_covered": False,
                    "composition_covered": False,
                    "confidence": 0.0,
                    "rationale": "LLM error — defaulted to no-license",
                    "model": model,
                    "cache_hit": False,
                }
            )
            continue
        entry = LLMCacheEntry(
            patent_number=pn,
            process_covered=result.process_covered,
            composition_covered=result.composition_covered,
            confidence=result.confidence,
            rationale=result.rationale,
            model=model,
            ts=datetime.now(tz=timezone.utc).isoformat(),
        )
        append_cache(cache_path, entry)
        rows.append(_to_row(entry, cache_hit=False))

    df = pl.DataFrame(rows, schema=LLM_CLASSIFICATION_SCHEMA)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path)
    return df


def _smiles_index(cpc: pl.DataFrame, reactions: pl.DataFrame) -> dict[str, list[str]]:
    if "reaction_smiles" not in reactions.columns:
        return {}
    joined = cpc.select("rxn_id", "patent_number").join(
        reactions.select("rxn_id", "reaction_smiles"), on="rxn_id", how="inner"
    )
    out: dict[str, list[str]] = {}
    for r in joined.iter_rows(named=True):
        out.setdefault(r["patent_number"], []).append(r["reaction_smiles"])
    return out


def _call_with_retry(
    *,
    client: Any,
    model: str,
    patent_number: str,
    abstract: str | None,
    claims_text: str | None,
    smiles_examples: list[str],
    max_retries: int,
    backoff_seconds: float,
) -> LLMClassificationResult | None:
    for attempt in range(max_retries):
        try:
            return classify_patent_llm(
                client=client,
                patent_number=patent_number,
                title=None,
                abstract=abstract,
                claims_text=claims_text,
                reaction_smiles_examples=smiles_examples,
                model=model,
            )
        except Exception as exc:
            log.warning(
                "LLM call failed (attempt %d/%d) for patent=%s: %s",
                attempt + 1, max_retries, patent_number, exc,
            )
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2**attempt))
    return None


def _to_row(entry: LLMCacheEntry, *, cache_hit: bool) -> dict:
    return {
        "patent_number": entry.patent_number,
        "process_covered": entry.process_covered,
        "composition_covered": entry.composition_covered,
        "confidence": entry.confidence,
        "rationale": entry.rationale,
        "model": entry.model,
        "cache_hit": cache_hit,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_patents_llm_classify.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/preprocessing/patents/llm_classify.py \
        tests/unit/test_patents_llm_classify.py
git commit -m "feat(licensing): add eager LLM batch classifier with cache + retry"
```

---

### Task 13: `aichemy patents classify-llm` CLI subcommand

**Files:**
- Modify: `src/aichemy/cli.py`

- [ ] **Step 1: Add the subcommand**

In `src/aichemy/cli.py`, add after `patents_classify_cpc`:

```python
@patents_app.command("classify-llm")
def patents_classify_llm(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Eagerly classify CPC-ambiguous active patents via Claude; cache results."""
    import os

    import anthropic

    from aichemy.preprocessing.io import (
        interim_path,
        licenses_path,
        patents_path,
        read_reactions,
    )
    from aichemy.preprocessing.patents.llm_classify import (
        classify_ambiguous_patents,
    )

    cfg = _load(config, override)
    cpc = pl.read_parquet(licenses_path(cfg, "cpc_classifications.parquet"))
    patents = pl.read_parquet(patents_path(cfg, "patent_metadata.parquet"))
    reactions = read_reactions(interim_path(cfg, "augmented", "reactions_full.parquet"))

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise typer.BadParameter(
            "ANTHROPIC_API_KEY not set; LLM classification cannot proceed."
        )

    client = anthropic.Anthropic()
    out_path = licenses_path(cfg, "llm_classifications.parquet")
    out = classify_ambiguous_patents(
        cpc=cpc,
        patents=patents,
        reactions=reactions,
        cache_path=cfg.licenses.cache_path,
        out_path=out_path,
        client=client,
        model=cfg.licenses.llm_model,
        max_retries=cfg.licenses.llm_max_retries,
    )
    n_hit = int(out["cache_hit"].sum())
    typer.echo(
        f"[patents classify-llm] {out.height} patents classified "
        f"({n_hit} cache hits, {out.height - n_hit} fresh) → {out_path}"
    )
```

- [ ] **Step 2: Verify CLI registers**

Run: `uv run aichemy patents classify-llm --help`
Expected: prints help.

- [ ] **Step 3: Commit**

```bash
git add src/aichemy/cli.py
git commit -m "feat(licensing): add 'aichemy patents classify-llm' CLI subcommand"
```

---

### Task 14: `augment_licenses` merge step (pure function)

**Files:**
- Create: `src/aichemy/preprocessing/augment/licenses.py`
- Test: `tests/unit/test_augment_licenses.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_augment_licenses.py`:

```python
import polars as pl

from aichemy.preprocessing.augment.licenses import augment_licenses


def _reactions(rxns):
    return pl.DataFrame(
        {
            "rxn_id": [r[0] for r in rxns],
            "source": [r[1] for r in rxns],
            "balanced": [True] * len(rxns),
        }
    )


def test_metanetx_rows_get_all_false():
    reactions = _reactions([("MNXR1", "metanetx")])
    cpc = pl.DataFrame(
        schema={
            "rxn_id": pl.Utf8,
            "patent_number": pl.Utf8,
            "patent_active": pl.Boolean,
            "cpc_ambiguous": pl.Boolean,
            "process_covered_cpc": pl.Boolean,
            "composition_covered_cpc": pl.Boolean,
        }
    )
    llm = pl.DataFrame(
        schema={
            "patent_number": pl.Utf8,
            "process_covered": pl.Boolean,
            "composition_covered": pl.Boolean,
        }
    )
    out = augment_licenses(reactions, cpc, llm)
    row = out.row(0, named=True)
    assert row["patent_active"] is False
    assert row["process_covered"] is False
    assert row["composition_covered"] is False


def test_uspto_unambiguous_uses_cpc():
    reactions = _reactions([("USPTO:A:0", "uspto")])
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:A:0"],
            "patent_number": ["A"],
            "patent_active": [True],
            "cpc_ambiguous": [False],
            "process_covered_cpc": [True],
            "composition_covered_cpc": [False],
        }
    )
    llm = pl.DataFrame(
        schema={
            "patent_number": pl.Utf8,
            "process_covered": pl.Boolean,
            "composition_covered": pl.Boolean,
        }
    )
    out = augment_licenses(reactions, cpc, llm)
    row = out.row(0, named=True)
    assert row["patent_active"] is True
    assert row["process_covered"] is True
    assert row["composition_covered"] is False


def test_uspto_ambiguous_uses_llm_when_present():
    reactions = _reactions([("USPTO:B:0", "uspto")])
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:B:0"],
            "patent_number": ["B"],
            "patent_active": [True],
            "cpc_ambiguous": [True],
            "process_covered_cpc": [False],
            "composition_covered_cpc": [False],
        }
    )
    llm = pl.DataFrame(
        {
            "patent_number": ["B"],
            "process_covered": [False],
            "composition_covered": [True],
        }
    )
    out = augment_licenses(reactions, cpc, llm)
    row = out.row(0, named=True)
    assert row["process_covered"] is False
    assert row["composition_covered"] is True


def test_uspto_ambiguous_falls_back_to_false_when_llm_missing():
    reactions = _reactions([("USPTO:C:0", "uspto")])
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:C:0"],
            "patent_number": ["C"],
            "patent_active": [True],
            "cpc_ambiguous": [True],
            "process_covered_cpc": [False],
            "composition_covered_cpc": [False],
        }
    )
    llm = pl.DataFrame(
        schema={
            "patent_number": pl.Utf8,
            "process_covered": pl.Boolean,
            "composition_covered": pl.Boolean,
        }
    )
    out = augment_licenses(reactions, cpc, llm)
    row = out.row(0, named=True)
    assert row["patent_active"] is True
    assert row["process_covered"] is False
    assert row["composition_covered"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_augment_licenses.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the merge**

Create `src/aichemy/preprocessing/augment/licenses.py`:

```python
"""Merge license classifications onto reactions.

Resolution rule:
- MetaNetX rows (no patent association) → all flags False.
- USPTO rows: for each (rxn_id, patent_number), if cpc_ambiguous AND a
  matching LLM row exists, use LLM; otherwise use CPC. Multi-patent
  reactions OR-aggregate across patents.
"""

from __future__ import annotations

import polars as pl


def augment_licenses(
    reactions: pl.DataFrame,
    cpc: pl.DataFrame,
    llm: pl.DataFrame,
) -> pl.DataFrame:
    """Add patent_active, process_covered, composition_covered columns."""
    # Join LLM onto CPC by patent_number; coalesce ambiguous rows to LLM's verdict.
    llm_renamed = llm.select(
        "patent_number",
        pl.col("process_covered").alias("process_covered_llm"),
        pl.col("composition_covered").alias("composition_covered_llm"),
    )
    resolved = (
        cpc.join(llm_renamed, on="patent_number", how="left")
        .with_columns(
            pl.when(pl.col("cpc_ambiguous") & pl.col("process_covered_llm").is_not_null())
            .then(pl.col("process_covered_llm"))
            .otherwise(pl.col("process_covered_cpc"))
            .alias("process_covered"),
            pl.when(pl.col("cpc_ambiguous") & pl.col("composition_covered_llm").is_not_null())
            .then(pl.col("composition_covered_llm"))
            .otherwise(pl.col("composition_covered_cpc"))
            .alias("composition_covered"),
        )
        .select(
            "rxn_id",
            "patent_active",
            "process_covered",
            "composition_covered",
        )
    )

    # OR-aggregate per rxn_id (in case multiple patents).
    aggregated = resolved.group_by("rxn_id").agg(
        pl.col("patent_active").any().alias("patent_active"),
        pl.col("process_covered").any().alias("process_covered"),
        pl.col("composition_covered").any().alias("composition_covered"),
    )

    # Left-join onto reactions; fill nulls with False (covers MetaNetX rows).
    out = (
        reactions.join(aggregated, on="rxn_id", how="left")
        .with_columns(
            pl.col("patent_active").fill_null(False),
            pl.col("process_covered").fill_null(False),
            pl.col("composition_covered").fill_null(False),
        )
    )
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_augment_licenses.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/preprocessing/augment/licenses.py \
        tests/unit/test_augment_licenses.py
git commit -m "feat(licensing): add augment_licenses merge step"
```

---

### Task 15: `aichemy augment licenses` CLI subcommand

**Files:**
- Modify: `src/aichemy/cli.py`

- [ ] **Step 1: Add the subcommand**

In `src/aichemy/cli.py`, add to the existing `augment_app` (alongside `augment yields`, `augment prices`, etc.):

```python
@augment_app.command("licenses")
def augment_licenses_cmd(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Merge CPC + LLM license classifications onto reactions."""
    from aichemy.preprocessing.augment.licenses import augment_licenses
    from aichemy.preprocessing.io import (
        interim_path,
        licenses_path,
        read_reactions,
        write_reactions,
    )

    cfg = _load(config, override)
    reactions = read_reactions(interim_path(cfg, "augmented", "reactions_full.parquet"))
    cpc = pl.read_parquet(licenses_path(cfg, "cpc_classifications.parquet"))
    llm_path = licenses_path(cfg, "llm_classifications.parquet")
    if llm_path.exists():
        llm = pl.read_parquet(llm_path)
    else:
        # Synthesize empty-but-typed LLM frame so the merge still runs.
        llm = pl.DataFrame(
            schema={
                "patent_number": pl.Utf8,
                "process_covered": pl.Boolean,
                "composition_covered": pl.Boolean,
            }
        )

    out = augment_licenses(reactions, cpc, llm)
    out_path = interim_path(cfg, "augmented", "reactions_licensed.parquet")
    write_reactions(out, out_path)

    n_proc = int(out["process_covered"].sum())
    n_comp = int(out["composition_covered"].sum())
    typer.echo(
        f"[augment licenses] {out.height} reactions "
        f"({n_proc} process-covered, {n_comp} composition-covered) → {out_path}"
    )
```

- [ ] **Step 2: Verify CLI registers**

Run: `uv run aichemy augment licenses --help`
Expected: prints help.

- [ ] **Step 3: Commit**

```bash
git add src/aichemy/cli.py
git commit -m "feat(licensing): add 'aichemy augment licenses' CLI subcommand"
```

---

### Task 16: Add royalty rate fields to `SolverConfig`

**Files:**
- Modify: `src/aichemy/solver/config.py`
- Test: `tests/unit/test_solver_config_royalty.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_solver_config_royalty.py`:

```python
from aichemy.solver.config import SolverConfig


def test_solver_config_has_royalty_defaults():
    cfg = SolverConfig()
    assert cfg.r_process == 0.0
    assert cfg.r_comp == 0.0


def test_solver_config_accepts_custom_royalties():
    cfg = SolverConfig(r_process=0.05, r_comp=0.03)
    assert cfg.r_process == 0.05
    assert cfg.r_comp == 0.03
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_solver_config_royalty.py -v`
Expected: FAIL — `AttributeError: r_process`.

- [ ] **Step 3: Add the fields**

Append to `class SolverConfig(BaseModel)` in `src/aichemy/solver/config.py` (before `output_path`):

```python
    # Royalty rate on process-covered reaction revenue (decimal, 0.0–1.0).
    # Default 0.0 means current behavior is unchanged when license data
    # is absent or rates aren't passed.
    r_process: float = 0.0

    # Royalty rate on composition-covered product revenue (decimal, 0.0–1.0).
    r_comp: float = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_solver_config_royalty.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/solver/config.py tests/unit/test_solver_config_royalty.py
git commit -m "feat(licensing): add r_process and r_comp to SolverConfig"
```

---

### Task 17: Subtract royalty terms from MILP objective

**Files:**
- Modify: `src/aichemy/solver/model.py`
- Test: `tests/unit/test_solver_royalty.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_solver_royalty.py`:

```python
import polars as pl

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import build_and_solve


def _two_reaction_fixture(*, process_covered: bool, composition_covered: bool):
    """Single reaction A + B → C; price A=$1/g, B=$1/g, C=$10/g; yield 1.0."""
    reactions = pl.DataFrame(
        {
            "rxn_id": ["RX1"],
            "yield_rate": [1.0],
            "reactants": [
                [
                    {"mol_id": "A", "coefficient": 1.0},
                    {"mol_id": "B", "coefficient": 1.0},
                ]
            ],
            "products": [[{"mol_id": "C", "coefficient": 1.0}]],
            "balanced": [True],
            "patent_active": [process_covered or composition_covered],
            "process_covered": [process_covered],
            "composition_covered": [composition_covered],
        }
    )
    molecules = pl.DataFrame(
        {
            "mol_id": ["A", "B", "C"],
            "price_per_gram": [1.0, 1.0, 10.0],
        }
    )
    return reactions, molecules


def test_zero_royalty_matches_baseline_objective():
    reactions, molecules = _two_reaction_fixture(process_covered=True, composition_covered=True)
    sol_zero = build_and_solve(
        reactions, molecules, SolverConfig(r_process=0.0, r_comp=0.0)
    )
    # Drop license columns to simulate pre-licensing solver
    reactions_legacy = reactions.drop(["patent_active", "process_covered", "composition_covered"])
    sol_legacy = build_and_solve(reactions_legacy, molecules, SolverConfig())
    assert abs(sol_zero.objective_value - sol_legacy.objective_value) < 1e-3


def test_process_royalty_reduces_objective_by_expected_amount():
    reactions, molecules = _two_reaction_fixture(process_covered=True, composition_covered=False)
    cfg_no = SolverConfig(r_process=0.0, r_comp=0.0)
    cfg_p = SolverConfig(r_process=0.5, r_comp=0.0)
    sol_no = build_and_solve(reactions, molecules, cfg_no)
    sol_p = build_and_solve(reactions, molecules, cfg_p)
    # At r_process=0.5, half the product revenue is paid as royalty.
    # Expected drop = 0.5 * price_sell[C] * yield * f
    # Both solutions converge on f at max_flow if profitable; even with
    # the royalty, RX1 is profitable (10 - 0.5*10 - 1 - 1 = 3 > 0).
    expected_delta = 0.5 * 10.0 * 1.0 * sol_no.activated_reactions[0]["flow"]
    assert abs((sol_no.objective_value - sol_p.objective_value) - expected_delta) < 1e-2


def test_composition_royalty_reduces_objective_by_expected_amount():
    reactions, molecules = _two_reaction_fixture(process_covered=False, composition_covered=True)
    sol_no = build_and_solve(
        reactions, molecules, SolverConfig(r_process=0.0, r_comp=0.0)
    )
    sol_c = build_and_solve(
        reactions, molecules, SolverConfig(r_process=0.0, r_comp=0.5)
    )
    sold_qty = next(s for s in sol_no.sold_molecules if s["mol_id"] == "C")["quantity"]
    expected_delta = 0.5 * 10.0 * sold_qty
    assert abs((sol_no.objective_value - sol_c.objective_value) - expected_delta) < 1e-2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_solver_royalty.py -v`
Expected: FAIL — objective unchanged when royalties applied.

- [ ] **Step 3: Modify `build_and_solve` to read license columns and add royalty terms**

In `src/aichemy/solver/model.py`, modify the rxn_meta-building loop (lines 96-114) to capture process coverage:

```python
    referenced: set[str] = set()
    rxn_meta: list[dict[str, Any]] = []
    for row in reactions.iter_rows(named=True):
        rxn_id = row["rxn_id"]
        yield_rate = row.get("yield_rate") or 0.85
        reactants = [
            (stoich["mol_id"], float(stoich["coefficient"])) for stoich in row["reactants"]
        ]
        products = [(stoich["mol_id"], float(stoich["coefficient"])) for stoich in row["products"]]
        for mol_id, _ in reactants + products:
            referenced.add(mol_id)
        rxn_meta.append(
            {
                "rxn_id": rxn_id,
                "yield_rate": yield_rate,
                "reactants": reactants,
                "products": products,
                "process_covered": bool(row.get("process_covered") or False),
            }
        )
```

Add a per-molecule `composition_covered` lookup. After the rxn_meta loop, before the price lookup:

```python
    composition_covered: set[str] = set()
    if "composition_covered" in molecules.columns:
        for r in molecules.iter_rows(named=True):
            if r.get("composition_covered"):
                composition_covered.add(r["mol_id"])
```

Modify the objective construction (lines 147-151):

```python
    # Objective: sell revenue − buy cost − process royalty − composition royalty
    revenue = pulp.lpSum(price_lookup[m][1] * q_sell[m] for m in referenced)
    cost = pulp.lpSum(price_lookup[m][0] * q_buy[m] for m in referenced)

    process_royalty = pulp.lpSum(
        config.r_process
        * sum(price_lookup[mid][1] for (mid, _) in m["products"])
        * m["yield_rate"]
        * f[m["rxn_id"]]
        for m in rxn_meta
        if m["process_covered"]
    )
    composition_royalty = pulp.lpSum(
        config.r_comp * price_lookup[m][1] * q_sell[m]
        for m in referenced
        if m in composition_covered
    )

    prob += (revenue - cost - process_royalty - composition_royalty, "total_profit")
```

Note: `composition_covered` on the reactions side now needs to flow to the molecules level. Since the data flow has it on reactions (per spec — `composition_covered` is a reaction column meaning "this reaction's products/intermediates are composition-covered"), we need to also propagate it to molecules. **Add this normalization step at the start of `build_and_solve`** (after the balanced filter):

```python
    # Reaction-level composition_covered → molecule-level: any product of a
    # composition-covered reaction is itself composition-covered for royalty.
    if "composition_covered" in reactions.columns:
        comp_mol_ids: set[str] = set()
        for row in reactions.iter_rows(named=True):
            if row.get("composition_covered"):
                for stoich in row["products"]:
                    comp_mol_ids.add(stoich["mol_id"])
        # Annotate molecules dataframe with the boolean (left-join via map)
        molecules = molecules.with_columns(
            pl.col("mol_id").is_in(list(comp_mol_ids)).alias("composition_covered")
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_solver_royalty.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the existing solver tests to confirm no regression**

Run: `uv run pytest tests/unit/test_solver.py -v`
Expected: PASS (existing tests should pass — license columns absent → all-False default → zero royalty terms).

- [ ] **Step 6: Commit**

```bash
git add src/aichemy/solver/model.py tests/unit/test_solver_royalty.py
git commit -m "feat(licensing): subtract process/composition royalty terms in MILP objective"
```

---

### Task 18: `aichemy solve sweep` CLI subcommand

**Files:**
- Modify: `src/aichemy/solver/cli.py`
- Test: `tests/unit/test_solve_sweep.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_solve_sweep.py`:

```python
import json
from pathlib import Path

import polars as pl

from aichemy.solver.cli import _run_sweep
from aichemy.solver.config import SolverConfig


def _fixture():
    reactions = pl.DataFrame(
        {
            "rxn_id": ["RX1"],
            "yield_rate": [1.0],
            "reactants": [[{"mol_id": "A", "coefficient": 1.0}]],
            "products": [[{"mol_id": "C", "coefficient": 1.0}]],
            "balanced": [True],
            "patent_active": [True],
            "process_covered": [True],
            "composition_covered": [True],
        }
    )
    molecules = pl.DataFrame({"mol_id": ["A", "C"], "price_per_gram": [1.0, 10.0]})
    return reactions, molecules


def test_sweep_writes_summary_with_one_row_per_grid_point(tmp_path: Path):
    reactions, molecules = _fixture()
    summary = _run_sweep(
        reactions, molecules,
        r_process_grid=[0.0, 0.05],
        r_comp_grid=[0.0, 0.05],
        out_dir=tmp_path,
        base_config=SolverConfig(),
    )
    assert summary.height == 4
    assert set(summary.columns) >= {
        "r_process", "r_comp", "objective_value",
        "n_active_reactions", "n_sold_products", "set_hash", "infeasible",
    }
    assert (tmp_path / "summary.parquet").exists()


def test_sweep_set_hash_changes_when_active_set_changes(tmp_path: Path):
    """At very high royalty, the optimal solution drops the patent-covered route."""
    reactions, molecules = _fixture()
    summary = _run_sweep(
        reactions, molecules,
        r_process_grid=[0.0, 0.99],
        r_comp_grid=[0.0],
        out_dir=tmp_path,
        base_config=SolverConfig(),
    )
    hashes = summary["set_hash"].to_list()
    # Low and very-high royalty should produce different active sets.
    assert hashes[0] != hashes[1]


def test_sweep_writes_per_cell_solution_files(tmp_path: Path):
    reactions, molecules = _fixture()
    _run_sweep(
        reactions, molecules,
        r_process_grid=[0.0],
        r_comp_grid=[0.0],
        out_dir=tmp_path,
        base_config=SolverConfig(),
    )
    cells = list((tmp_path / "runs").glob("r_process_*_r_comp_*"))
    assert len(cells) == 1
    sol = json.loads((cells[0] / "solution.json").read_text())
    assert "objective_value" in sol
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_solve_sweep.py -v`
Expected: FAIL — `ImportError: _run_sweep`.

- [ ] **Step 3: Implement `_run_sweep` and the `sweep` subcommand in `solver/cli.py`**

Append to `src/aichemy/solver/cli.py`:

```python
import hashlib
import json as _json

import polars as pl


def _run_sweep(
    reactions: pl.DataFrame,
    molecules: pl.DataFrame,
    *,
    r_process_grid: list[float],
    r_comp_grid: list[float],
    out_dir: Path,
    base_config: SolverConfig,
) -> pl.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for rp in r_process_grid:
        for rc in r_comp_grid:
            cfg = base_config.model_copy(update={"r_process": rp, "r_comp": rc})
            sol = build_and_solve(reactions, molecules, cfg)
            cell_dir = out_dir / "runs" / f"r_process_{rp:.4f}_r_comp_{rc:.4f}"
            cell_dir.mkdir(parents=True, exist_ok=True)
            (cell_dir / "solution.json").write_text(
                _json.dumps(sol.to_dict(), indent=2) + "\n"
            )
            sold_ids = sorted(s["mol_id"] for s in sol.sold_molecules)
            set_hash = hashlib.sha256(
                ",".join(sold_ids).encode()
            ).hexdigest()[:16]
            rows.append(
                {
                    "r_process": rp,
                    "r_comp": rc,
                    "objective_value": float(sol.objective_value)
                    if sol.status == "Optimal"
                    else None,
                    "n_active_reactions": len(sol.activated_reactions),
                    "n_sold_products": len(sol.sold_molecules),
                    "set_hash": set_hash,
                    "infeasible": sol.status == "Infeasible",
                }
            )
    summary = pl.DataFrame(rows)
    summary.write_parquet(out_dir / "summary.parquet")
    return summary


@solver_app.command("sweep")
def sweep(
    config: Path = _ConfigOpt,
    override: list[Path] = _OverrideOpt,
    r_process: str = typer.Option(
        "0,0.02,0.04,0.06,0.08", "--r-process",
        help="Comma-separated decimal fractions for the process royalty axis.",
    ),
    r_comp: str = typer.Option(
        "0,0.02,0.04,0.06,0.08", "--r-comp",
        help="Comma-separated decimal fractions for the composition royalty axis.",
    ),
    out: Path = typer.Option(
        Path("data/processed/sensitivity"), "--out",
        help="Output directory.",
    ),
    backend: str = _BackendOpt,
    verbose: bool = _VerboseOpt,
) -> None:
    """Sweep the (r_process, r_comp) grid; write per-cell solutions + summary parquet."""
    cfg = load_config(config, override)
    base_cfg = SolverConfig(
        backend=backend,  # type: ignore[arg-type]
        verbose=verbose,
        output_path=processed_path(cfg, "solution.json"),
    )
    reactions = read_reactions(processed_path(cfg, "reactions.parquet"))
    molecules = read_molecules(processed_path(cfg, "molecules.parquet"))

    rp_grid = [float(x) for x in r_process.split(",")]
    rc_grid = [float(x) for x in r_comp.split(",")]
    typer.echo(
        f"[solve sweep] {len(rp_grid)}×{len(rc_grid)} = {len(rp_grid) * len(rc_grid)} cells"
    )
    summary = _run_sweep(
        reactions, molecules,
        r_process_grid=rp_grid, r_comp_grid=rc_grid,
        out_dir=out, base_config=base_cfg,
    )
    typer.echo(
        f"[solve sweep] complete; summary → {out / 'summary.parquet'} "
        f"({summary.height} rows)"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_solve_sweep.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Verify CLI registers**

Run: `uv run aichemy solve sweep --help`
Expected: prints help.

- [ ] **Step 6: Commit**

```bash
git add src/aichemy/solver/cli.py tests/unit/test_solve_sweep.py
git commit -m "feat(licensing): add 'aichemy solve sweep' subcommand for sensitivity"
```

---

### Task 19: Wire new stages into `dvc.yaml`

**Files:**
- Modify: `dvc.yaml`

- [ ] **Step 1: Locate the existing `augment_directionality` stage**

Open `dvc.yaml` and find the stage that produces `data/interim/augmented/reactions_full.parquet` (the existing `augment_directionality` stage, near the bottom).

- [ ] **Step 2: Insert the four new stages between `augment_directionality` and `export`**

Add after `augment_directionality` and before `export`:

```yaml
  fetch_patent_metadata:
    cmd: uv run aichemy patents fetch --config configs/default.yaml
    deps:
      - configs/default.yaml
      - src/aichemy/preprocessing/patents/fetch.py
      - data/interim/augmented/reactions_full.parquet
    outs:
      - data/interim/patents/patent_metadata.parquet

  classify_licenses_cpc:
    cmd: uv run aichemy patents classify-cpc --config configs/default.yaml
    deps:
      - configs/default.yaml
      - config/cpc_rules.yaml
      - src/aichemy/preprocessing/patents/cpc.py
      - data/interim/augmented/reactions_full.parquet
      - data/interim/patents/patent_metadata.parquet
    outs:
      - data/interim/licenses/cpc_classifications.parquet

  classify_licenses_llm:
    cmd: uv run aichemy patents classify-llm --config configs/default.yaml
    deps:
      - configs/default.yaml
      - src/aichemy/preprocessing/patents/llm_classify.py
      - src/aichemy/preprocessing/patents/cache.py
      - data/interim/licenses/cpc_classifications.parquet
      - data/interim/patents/patent_metadata.parquet
    outs:
      - data/interim/licenses/llm_classifications.parquet
      - data/interim/licenses/llm_cache.jsonl

  augment_licenses:
    cmd: uv run aichemy augment licenses --config configs/default.yaml
    deps:
      - configs/default.yaml
      - src/aichemy/preprocessing/augment/licenses.py
      - data/interim/augmented/reactions_full.parquet
      - data/interim/licenses/cpc_classifications.parquet
      - data/interim/licenses/llm_classifications.parquet
    outs:
      - data/interim/augmented/reactions_licensed.parquet
```

- [ ] **Step 3: Update the `export` stage to read from `reactions_licensed.parquet`**

Find the existing `export` stage in `dvc.yaml`. Change its `deps` so it depends on `reactions_licensed.parquet` instead of `reactions_full.parquet`:

```yaml
  export:
    cmd: uv run aichemy export --config configs/default.yaml
    deps:
      - configs/default.yaml
      - src/aichemy/preprocessing/export.py
      - data/interim/augmented/reactions_licensed.parquet
      - data/interim/augmented/molecules_priced.parquet
    outs:
      - data/processed/reactions.parquet
      - data/processed/molecules.parquet
      - data/processed/hypergraph_manifest.json
```

Also update `src/aichemy/preprocessing/export.py` (find the line that reads `reactions_full.parquet`) to instead read `reactions_licensed.parquet`. The change is one path string in that file.

- [ ] **Step 4: Validate the DAG**

Run: `uv run dvc dag` (prints the DAG textually).
Expected: the four new stages appear between `augment_directionality` and `export`.

Run: `uv run dvc repro --dry`
Expected: dry-run output shows the new stages in the right order, no cycles.

- [ ] **Step 5: Commit**

```bash
git add dvc.yaml src/aichemy/preprocessing/export.py
git commit -m "feat(licensing): wire patent fetch + license stages into DVC pipeline"
```

---

### Task 20: End-to-end integration test (DVC repro on tiny fixture)

**Files:**
- Create: `tests/integration/test_dvc_repro_licenses.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_dvc_repro_licenses.py`:

```python
"""End-to-end integration test for the licensing stages.

Runs the four new pipeline stages on a tiny synthetic fixture, with
PatentsView calls stubbed via `responses` and Anthropic calls stubbed via
monkeypatching the SDK class. Verifies the data flows through to
`reactions_licensed.parquet` with correct columns.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl
import pytest
import responses


PATENTSVIEW = "https://search.patentsview.org/api/v1/patent"


@pytest.fixture
def fake_reactions_full(tmp_path: Path) -> Path:
    df = pl.DataFrame(
        {
            "rxn_id": ["USPTO:7456123:0", "MNXR1"],
            "reaction_smiles": ["A.B>>C", "X>>Y"],
            "reactants": [
                [{"mol_id": "A", "coefficient": 1.0}, {"mol_id": "B", "coefficient": 1.0}],
                [{"mol_id": "X", "coefficient": 1.0}],
            ],
            "products": [
                [{"mol_id": "C", "coefficient": 1.0}],
                [{"mol_id": "Y", "coefficient": 1.0}],
            ],
            "type": ["chemical", "enzymatic"],
            "yield_rate": [0.85, 0.95],
            "delta_g": [None, None],
            "balanced": [True, True],
            "source": ["uspto", "metanetx"],
        }
    )
    out = tmp_path / "reactions_full.parquet"
    df.write_parquet(out)
    return out


@responses.activate
def test_full_license_flow_with_stubbed_apis(
    tmp_path: Path,
    fake_reactions_full: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    # Stub PatentsView
    responses.add(
        responses.POST,
        PATENTSVIEW,
        json={
            "patents": [
                {
                    "patent_number": "7456123",
                    "patent_date": "2008-11-25",
                    "patent_abstract": "A medicinal preparation for…",
                    "claims": [{"text": "1. A composition comprising…"}],
                    "cpcs": [{"cpc_group_id": "A61K 31/505"}],
                    "assignees": [{"assignee_organization": "Acme"}],
                    "application": {"filing_date": "2015-03-14"},
                }
            ]
        },
        status=200,
    )

    # Stub Anthropic
    fake_block = MagicMock()
    fake_block.type = "tool_use"
    fake_block.name = "report_classification"
    fake_block.input = {
        "process_covered": False,
        "composition_covered": True,
        "confidence": 0.9,
        "rationale": "Independent claim 1 is composition-of-matter.",
    }
    fake_msg = MagicMock()
    fake_msg.stop_reason = "tool_use"
    fake_msg.content = [fake_block]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **kw: fake_client)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    # Run each pipeline step in sequence
    from aichemy.preprocessing.patents.cpc import (
        classify_dataframe,
        load_cpc_rules,
    )
    from aichemy.preprocessing.patents.fetch import (
        fetch_patents,
        write_metadata_parquet,
    )
    from aichemy.preprocessing.patents.llm_classify import (
        classify_ambiguous_patents,
    )
    from aichemy.preprocessing.augment.licenses import augment_licenses
    from datetime import date

    reactions = pl.read_parquet(fake_reactions_full)

    # 1. fetch
    items = fetch_patents(["7456123"], endpoint=PATENTSVIEW, max_retries=1)
    patents_path = tmp_path / "patent_metadata.parquet"
    write_metadata_parquet(items, patents_path)

    # 2. classify-cpc
    rules = load_cpc_rules(Path("config/cpc_rules.yaml"))
    cpc_df = classify_dataframe(
        reactions, pl.read_parquet(patents_path),
        rules=rules, today=date(2026, 4, 25),
    )
    cpc_path = tmp_path / "cpc.parquet"
    cpc_df.write_parquet(cpc_path)

    # 3. classify-llm
    llm_df = classify_ambiguous_patents(
        cpc=cpc_df,
        patents=pl.read_parquet(patents_path),
        reactions=reactions,
        cache_path=tmp_path / "cache.jsonl",
        out_path=tmp_path / "llm.parquet",
        client=fake_client,
        model="claude-haiku-4-5",
        max_retries=1,
    )

    # 4. augment_licenses (merge)
    out = augment_licenses(reactions, cpc_df, llm_df)

    # Assertions
    assert "patent_active" in out.columns
    by_rxn = {r["rxn_id"]: r for r in out.iter_rows(named=True)}
    assert by_rxn["USPTO:7456123:0"]["patent_active"] is True
    assert by_rxn["USPTO:7456123:0"]["composition_covered"] is True
    assert by_rxn["USPTO:7456123:0"]["process_covered"] is False
    assert by_rxn["MNXR1"]["patent_active"] is False
    assert by_rxn["MNXR1"]["composition_covered"] is False
```

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest tests/integration/test_dvc_repro_licenses.py -v`
Expected: PASS.

- [ ] **Step 3: Run the full test suite to confirm no regressions**

Run: `uv run pytest -x`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_dvc_repro_licenses.py
git commit -m "test(licensing): end-to-end integration test for licensing pipeline"
```

---

## Verification Checklist

After all 20 tasks complete, the engineer should be able to:

- [ ] Run `uv run aichemy patents --help` and see `fetch`, `classify-cpc`, `classify-llm` subcommands.
- [ ] Run `uv run aichemy augment licenses --help` and see the merge subcommand.
- [ ] Run `uv run aichemy solve sweep --help` and see the sensitivity subcommand.
- [ ] Run `uv run dvc dag` and see the four new stages in the right place.
- [ ] Run `uv run pytest` and have all tests pass (including legacy `test_solver.py`).
- [ ] Read `data/processed/reactions.parquet` (after a full pipeline run) and find columns `patent_active`, `process_covered`, `composition_covered`.
- [ ] Run a 5×5 sweep on a small fixture and inspect `data/processed/sensitivity/summary.parquet`.

## Out-of-scope (per spec)

- Composition-of-matter lookup keyed by InChIKey (would catch products patented in *different* patents than the reaction was extracted from).
- Patent term extensions (Hatch-Waxman, terminal disclaimers).
- Maintenance-fee status checks (the `patent_active` flag is purely filing-date based).
- International patents (Lowe data is USPTO-only).
- Fixed annual access fees / lump-sum license fees.

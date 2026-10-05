# Stage 01 — fetch-raw

> **Execution:** Ralph Loop, `--max-iterations 30`, promise `STAGE 01 COMPLETE`.
> **Blocks on:** Open Item 04 (pinned raw-data URLs).

**Goal:** Replace the `aichemy fetch-raw` CLI stub with real downloads of MetaNetX reference files (`reac_prop.tsv`, `chem_prop.tsv`, `reac_xref.tsv`, `chem_xref.tsv`) and the USPTO Lowe reaction SMILES dump into `data/raw/metanetx/` and `data/raw/uspto/`.

**Status at foundation completion:** Stub creates empty directories; no downloads.

**Architecture:** URL table lives in `configs/default.yaml` under `sources.urls.metanetx` and `sources.urls.uspto`. `aichemy.preprocessing.sources.fetch` module implements idempotent downloads using `httpx` (add to dependencies). Skip if file exists and checksum matches; otherwise stream to disk with tqdm progress. SHA256 checksums also in config.

## Tasks

### T1: Add `sources.urls` + checksums to config model

- [ ] Extend `SourcesConfig` with `urls: dict[str, str]` and `checksums: dict[str, str]` (or a `SourceURL(BaseModel){ url, sha256 }` substructure)
- [ ] Unit test: default config validates without urls (empty dicts), with urls parses cleanly
- [ ] Commit

### T2: Add `httpx` dependency + fetch helper

- [ ] Add `httpx>=0.27` to `pyproject.toml [project] dependencies`
- [ ] Create `src/aichemy/preprocessing/sources/fetch.py` with `download(url: str, dest: Path, expected_sha256: str | None = None) -> None` — streams to disk, verifies sha256 if given, skips if target exists and hash matches
- [ ] Test with `pytest-httpx` (add to dev dependencies) mocking `http://fake/file` → deterministic bytes; verify hash mismatch raises
- [ ] Commit

### T3: Wire `fetch-raw` CLI to real downloads

- [ ] Replace the stub body: iterate `cfg.sources.urls.metanetx` items, call `download(...)` for each into `raw_path(cfg, "metanetx", filename)`. Same for USPTO.
- [ ] Integration test with `pytest-httpx`: mock a trivially small file, verify it lands in `data/raw/metanetx/`
- [ ] Commit

### T4: Update `configs/default.yaml` with canonical URLs

- [ ] **BLOCKED** pending Open Item 04. Once URLs pinned, drop them in and record SHA256s.
- [ ] Commit

### T5: End-to-end verification

- [ ] `uv run dvc repro fetch_raw` — should succeed with real files (skipped if cached)
- [ ] `uv run pytest` — all tests still green
- [ ] Commit + push

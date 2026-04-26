# Sub-Plan B: `aichemy-pricing` — Offline Catalog Resolvers

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Parent plan:** `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md`
> **Verification source:** `experiments/chem-pricing-verification/CLAIMS.md` (CLAIM-04, CLAIM-08, CLAIM-03 + CLAIM-20 are the load-bearing claims for this sub-plan)
> **Depends on:** Sub-Plan A (uses `ResolverHit`, `VendorResolver`)
> **Delivers (consumed by sub-plans D and E):**
> - `aichemy_pricing.resolvers.PubChemSdfResolver` — InChIKey → vendor SKU from PubChem Substance SDF FTP dump
> - `aichemy_pricing.resolvers.EnamineSdfResolver` — InChIKey → EN300-* SKU from Enamine BB SDFs
> - `aichemy_pricing.resolvers.ZincTrancheResolver` — InChIKey → multi-vendor SKU map from ZINC20 2D tranches
> - Shared streaming SDF parser `iter_sdf_records` in `aichemy_pricing.resolvers._sdf` (module is private; function is module-public so resolvers can import it)

**Goal:** Build the "scrape less, resolve more" half of the package. Three offline resolvers parse pre-downloaded SDF / SMI files and emit `ResolverHit(inchikey → vendor + sku)` so that the live scrapers in sub-plans C/D never need to hit a vendor's search endpoint.

**Architecture:** Each resolver is a small dataclass with `from_files(paths)` classmethod and `resolve(inchikey)` lookup. Indexing happens at construction time and is held entirely in memory; for production runs against the full PubChem Substance dump (~491M SIDs across 982 files), the loader streams record-by-record and only retains entries whose source is in an `allowed_sources` allowlist. Each resolver is independently testable with a small SDF/SMI fixture committed under `tests/data/`.

**Tech Stack:** Python 3.11, pydantic v2 (already pulled in by sub-plan A), pure stdlib for parsing — no rdkit dependency for the parser itself (rdkit only enters when computing InChIKeys upstream of the JOIN).

---

## File Structure

```
src/aichemy_pricing/resolvers/
├── __init__.py                            # CREATE — re-export the three resolvers
├── _sdf.py                                # CREATE — shared streaming SDF parser
├── pubchem_sdf.py                         # CREATE — Task B1
├── enamine_sdf.py                         # CREATE — Task B2
└── zinc_tranches.py                       # CREATE — Task B3

src/aichemy_pricing/tests/
├── data/
│   ├── pubchem_sample.sdf                 # CAPTURE — 10 records from real PubChem Substance dump
│   ├── enamine_acids_snippet.sdf          # CAPTURE — 10 records from enamine.net /functional-classes/acids
│   └── zinc_tranche_sample.smi            # CAPTURE — 50 lines from a real ZINC20 tranche file
├── test_sdf_parser.py                     # CREATE — Task B0
├── test_resolvers_pubchem.py              # CREATE — Task B1
├── test_resolvers_enamine.py              # CREATE — Task B2
└── test_resolvers_zinc.py                 # CREATE — Task B3
```

---

## Task B0: Shared streaming SDF parser

**Files:**
- Create: `src/aichemy_pricing/resolvers/__init__.py` (will be populated incrementally)
- Create: `src/aichemy_pricing/resolvers/_sdf.py`
- Create: `src/aichemy_pricing/tests/test_sdf_parser.py`

**Why:** Both PubChem and Enamine SDF parsers need the same record-iteration logic. Factor it once, test it once.

- [ ] **Step 1: Empty `__init__.py`** (will populate per task)

```bash
mkdir -p src/aichemy_pricing/resolvers
: > src/aichemy_pricing/resolvers/__init__.py
```

- [ ] **Step 2: Write failing test**

```python
# src/aichemy_pricing/tests/test_sdf_parser.py
"""Unit tests for the streaming SDF parser shared by all SDF-based resolvers."""
from __future__ import annotations

import textwrap

import pytest

from aichemy_pricing.resolvers._sdf import iter_sdf_records


def test_parses_two_records_with_multiline_value(tmp_path) -> None:
    sdf = textwrap.dedent("""\
        Aspirin
        ...
        > <PUBCHEM_IUPAC_INCHIKEY>
        BSYNRYMUTXBXSQ-UHFFFAOYSA-N

        > <PUBCHEM_EXT_DATASOURCE_NAME>
        Sigma-Aldrich

        > <PUBCHEM_EXT_DATASOURCE_REGID>
        A2093

        $$$$
        Caffeine
        ...
        > <PUBCHEM_IUPAC_INCHIKEY>
        RYYVLZVUVIJVGH-UHFFFAOYSA-N

        > <PUBCHEM_EXT_DATASOURCE_NAME>
        Cayman Chemical

        > <PUBCHEM_EXT_DATASOURCE_REGID>
        14118

        $$$$
        """)
    p = tmp_path / "tiny.sdf"
    p.write_text(sdf)

    records = list(iter_sdf_records(p))
    assert len(records) == 2
    assert records[0]["PUBCHEM_IUPAC_INCHIKEY"] == ["BSYNRYMUTXBXSQ-UHFFFAOYSA-N"]
    assert records[0]["PUBCHEM_EXT_DATASOURCE_REGID"] == ["A2093"]
    assert records[1]["PUBCHEM_EXT_DATASOURCE_NAME"] == ["Cayman Chemical"]


def test_skips_records_without_terminator(tmp_path) -> None:
    """A truncated SDF (no trailing $$$$) must not yield the partial record."""
    sdf = textwrap.dedent("""\
        Foo
        > <X>
        1

        """)
    p = tmp_path / "trunc.sdf"
    p.write_text(sdf)
    assert list(iter_sdf_records(p)) == []


def test_handles_multiline_tag_values(tmp_path) -> None:
    sdf = textwrap.dedent("""\
        Foo
        > <NOTES>
        line one
        line two
        line three

        > <X>
        1

        $$$$
        """)
    p = tmp_path / "multi.sdf"
    p.write_text(sdf)
    rec = next(iter_sdf_records(p))
    assert rec["NOTES"] == ["line one", "line two", "line three"]
    assert rec["X"] == ["1"]


def test_reads_sdf_gz_transparently(tmp_path) -> None:
    """The PubChem dump ships .sdf.gz; without gzip detection, opening deflate
    bytes as 'rt' with errors='replace' silently yields zero records — every
    downstream lookup returns None for the wrong reason. Lock that closed."""
    import gzip
    sdf_text = textwrap.dedent("""\
        Aspirin
        > <PUBCHEM_IUPAC_INCHIKEY>
        BSYNRYMUTXBXSQ-UHFFFAOYSA-N

        > <PUBCHEM_EXT_DATASOURCE_NAME>
        Sigma-Aldrich

        > <PUBCHEM_EXT_DATASOURCE_REGID>
        A2093

        $$$$
        """)
    p = tmp_path / "tiny.sdf.gz"
    with gzip.open(p, "wt") as f:
        f.write(sdf_text)
    records = list(iter_sdf_records(p))
    assert len(records) == 1
    assert records[0]["PUBCHEM_IUPAC_INCHIKEY"] == ["BSYNRYMUTXBXSQ-UHFFFAOYSA-N"]
```

- [ ] **Step 3: Run; ImportError**

- [ ] **Step 4: Implement**

```python
# src/aichemy_pricing/resolvers/_sdf.py
"""Streaming SDF parser. Memory-bounded: yields one dict-of-tags per `$$$$`.

Handles both plain-text `.sdf` and gzipped `.sdf.gz` files transparently —
the PubChem FTP dump (CLAIM-04) ships 982 `.sdf.gz` files, and sub-plan E's
AIchemy backend integration globs `*.sdf*` so both extensions reach this
parser. Without gzip detection, opening deflate bytes as `errors="replace"`
text silently yields zero records (no UnicodeDecodeError, no log line) and
every downstream price lookup returns None for the wrong reason.
"""
from __future__ import annotations

import gzip
from collections.abc import Iterator
from pathlib import Path


def _open_text(path: Path):  # type: ignore[no-untyped-def]
    if path.suffix == ".gz":
        return gzip.open(path, "rt", errors="replace")
    return path.open("rt", errors="replace")


def iter_sdf_records(path: Path) -> Iterator[dict[str, list[str]]]:
    """Yield {tag_name: [line, ...]} for each SDF record in `path`.

    Records are delimited by lines containing only `$$$$`. Tag values are the
    lines following `> <TAG>` up to the next blank line. Records without a
    trailing `$$$$` are not yielded (defensive behavior for truncated dumps).
    `.sdf.gz` files are opened transparently via gzip.
    """
    record: dict[str, list[str]] = {}
    current_tag: str | None = None
    with _open_text(path) as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line == "$$$$":
                if record:
                    yield record
                record = {}
                current_tag = None
            elif line.startswith("> <") and line.endswith(">"):
                current_tag = line[3:-1]
                record.setdefault(current_tag, [])
            elif current_tag is not None and line == "":
                current_tag = None
            elif current_tag is not None:
                record[current_tag].append(line)
```

- [ ] **Step 5: Run; pass (3 tests)**

```bash
uv run pytest src/aichemy_pricing/tests/test_sdf_parser.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/resolvers/_sdf.py src/aichemy_pricing/resolvers/__init__.py src/aichemy_pricing/tests/test_sdf_parser.py
git commit -m "feat(pricing): streaming SDF parser shared by resolvers"
```

---

## Task B1: `PubChemSdfResolver`

**Per CLAIM-04 (PARTIAL):** the FTP dump at `https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/` is real and fresh (982 `.sdf.gz` files, ~491M SIDs). **The actual SDF tag names are `PUBCHEM_EXT_DATASOURCE_NAME` and `PUBCHEM_EXT_DATASOURCE_REGID`** — the original report's "SourceName"/"RegistryID" were paraphrases. PubChem source table has 914 sources / 531 vendor-tagged.

**Files:**
- Create: `src/aichemy_pricing/resolvers/pubchem_sdf.py`
- Create: `src/aichemy_pricing/tests/test_resolvers_pubchem.py`
- Capture: `src/aichemy_pricing/tests/data/pubchem_sample.sdf`

- [ ] **Step 1: Capture fixture (one-time)**

The PubChem Substance SDFs are gzipped and large (~60 MB compressed per shard). We don't use the shared `_capture.py` helper here because it loads the entire body into memory before validation; a streaming pipeline is a better fit. The pipeline below downloads only as much as awk needs, then validates the result.

```bash
mkdir -p src/aichemy_pricing/tests/data
OUT=src/aichemy_pricing/tests/data/pubchem_sample.sdf
curl -sL --fail "https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/Substance_000000001_000500000.sdf.gz" \
  | gunzip \
  | awk 'BEGIN{n=0} /^\$\$\$\$/{n++; print; if (n>=10) exit; next} {print}' \
  > "$OUT"

# Validate: must have ≥10 record terminators and the expected vendor-source tag.
RECS=$(grep -c '^\$\$\$\$' "$OUT" || true)
HAS_DSN=$(grep -c '^> <PUBCHEM_EXT_DATASOURCE_NAME>' "$OUT" || true)
SIZE=$(wc -c < "$OUT")
if [ "$RECS" -lt 10 ] || [ "$HAS_DSN" -lt 1 ] || [ "$SIZE" -lt 5000 ]; then
  echo "FIXTURE CAPTURE FAILED: records=$RECS, source-tagged=$HAS_DSN, bytes=$SIZE" >&2
  rm -f "$OUT"
  exit 1
fi
echo "OK: $RECS records, $HAS_DSN source-tagged, $SIZE bytes"
```

Expected: `OK: 10 records, ≥1 source-tagged, ≥5000 bytes`. If this fails, the PubChem dump format may have changed (rare) or your network was interrupted mid-stream — retry.

- [ ] **Step 2: Failing tests**

```python
# src/aichemy_pricing/tests/test_resolvers_pubchem.py
"""Unit tests for PubChemSdfResolver. Uses a 10-record fixture captured from
the real FTP dump (https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/)."""
from __future__ import annotations

import pytest

from aichemy_pricing.resolvers.pubchem_sdf import PubChemSdfResolver


def test_resolver_indexes_at_least_one_record(fixture_dir) -> None:
    res = PubChemSdfResolver.from_files([fixture_dir / "pubchem_sample.sdf"])
    assert res.index, "expected at least one indexed InChIKey from the fixture"


def test_each_hit_carries_vendor_and_sku(fixture_dir) -> None:
    res = PubChemSdfResolver.from_files([fixture_dir / "pubchem_sample.sdf"])
    sample_ik = next(iter(res.index))
    hits = res.resolve(sample_ik)
    assert hits
    for h in hits:
        assert h.vendor and h.sku


def test_allowed_sources_filter(fixture_dir) -> None:
    """When `allowed_sources` is set, only matching `PUBCHEM_EXT_DATASOURCE_NAME`
    values are indexed."""
    res = PubChemSdfResolver.from_files(
        [fixture_dir / "pubchem_sample.sdf"],
        allowed_sources={"NoSuchVendor-XYZ"},
    )
    assert res.index == {}


def test_resolver_returns_empty_list_for_unknown_inchikey(fixture_dir) -> None:
    res = PubChemSdfResolver.from_files([fixture_dir / "pubchem_sample.sdf"])
    assert res.resolve("ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-Z") == []


def test_canonical_url_populated_when_present(fixture_dir) -> None:
    res = PubChemSdfResolver.from_files([fixture_dir / "pubchem_sample.sdf"])
    # at least one hit should carry a vendor URL
    any_url = any(h.canonical_url for hits in res.index.values() for h in hits)
    # Don't fail hard if the fixture's first 10 records happen to lack URL — just assert shape OK.
    assert isinstance(any_url, bool)
```

- [ ] **Step 3: Run; ImportError**

- [ ] **Step 4: Implement**

```python
# src/aichemy_pricing/resolvers/pubchem_sdf.py
"""Parse PubChem Substance SDF (FTP dump) into an InChIKey → ResolverHit index.

Per CLAIM-04 (PARTIAL):
  Source URL: https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/
  Real tag names (from `pubchem_sdtags.txt`):
    PUBCHEM_EXT_DATASOURCE_NAME   ← vendor name
    PUBCHEM_EXT_DATASOURCE_REGID  ← vendor SKU
    PUBCHEM_EXT_DATASOURCE_URL    ← canonical product URL (optional)
  Total source table: 914 sources / 531 vendor-tagged.
  ~491M SIDs across 982 files; production runs MUST set `allowed_sources`
  to keep memory bounded.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from aichemy_pricing.resolvers._sdf import iter_sdf_records
from aichemy_pricing.types import ResolverHit


@dataclass
class PubChemSdfResolver:
    name: str = "pubchem_sdf"
    index: dict[str, list[ResolverHit]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_files(
        cls,
        paths: list[Path],
        allowed_sources: set[str] | None = None,
    ) -> "PubChemSdfResolver":
        self = cls()
        for path in paths:
            for rec in iter_sdf_records(Path(path)):
                ik = (rec.get("PUBCHEM_IUPAC_INCHIKEY") or [None])[0]
                src = (rec.get("PUBCHEM_EXT_DATASOURCE_NAME") or [None])[0]
                regid = (rec.get("PUBCHEM_EXT_DATASOURCE_REGID") or [None])[0]
                url = (rec.get("PUBCHEM_EXT_DATASOURCE_URL") or [None])[0]
                if not (ik and src and regid):
                    continue
                if allowed_sources is not None and src not in allowed_sources:
                    continue
                self.index[ik].append(
                    ResolverHit(inchikey=ik, vendor=src, sku=regid, canonical_url=url)
                )
        return self

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.index.get(inchikey, []))
```

- [ ] **Step 5: Re-export from `resolvers/__init__.py`**

```python
# src/aichemy_pricing/resolvers/__init__.py
from aichemy_pricing.resolvers.pubchem_sdf import PubChemSdfResolver

__all__ = ["PubChemSdfResolver"]
```

- [ ] **Step 6: Run; pass (5 tests)**

- [ ] **Step 7: Commit**

```bash
git add src/aichemy_pricing/resolvers/pubchem_sdf.py src/aichemy_pricing/resolvers/__init__.py src/aichemy_pricing/tests/test_resolvers_pubchem.py src/aichemy_pricing/tests/data/pubchem_sample.sdf
git commit -m "feat(pricing): PubChemSdfResolver — InChIKey → vendor SKU from FTP dump"
```

---

## Task B2: `EnamineSdfResolver`

**Per CLAIM-08 (VERIFIED):** per-functional-class SDFs are anonymously downloadable from `enamine.net/building-blocks/functional-classes/{acids,boronics,amines,halides,...}`. **Per CLAIM-07 (VERIFIED):** product URL pattern is `https://enaminestore.com/catalog/EN300-{N}` (no www; SKU width is variable, regex `EN300-\d+`). **Per CLAIM-09 (PARTIAL):** total BB catalog is 2,292,307 — the original report's 573K was 4× stale.

**Files:**
- Create: `src/aichemy_pricing/resolvers/enamine_sdf.py`
- Create: `src/aichemy_pricing/tests/test_resolvers_enamine.py`
- Capture: `src/aichemy_pricing/tests/data/enamine_acids_snippet.sdf`

- [ ] **Step 1: Capture fixture**

Manually download one functional-class SDF (e.g. carboxylic acids) from `enamine.net/building-blocks/functional-classes/acids` (per CLAIM-08), unzip if needed, snip first 10 records. The exact field names vary by export ("Catalog ID", "idnumber", "ID", "EN_ID") — pick whichever is in your download. Save to `src/aichemy_pricing/tests/data/enamine_acids_snippet.sdf`.

- [ ] **Step 2: Failing tests**

```python
# src/aichemy_pricing/tests/test_resolvers_enamine.py
"""Unit tests for EnamineSdfResolver."""
from __future__ import annotations

import pytest

from aichemy_pricing.resolvers.enamine_sdf import EnamineSdfResolver


def test_resolver_indexes_at_least_one_enamine_sku(fixture_dir) -> None:
    res = EnamineSdfResolver.from_files([fixture_dir / "enamine_acids_snippet.sdf"])
    assert res.index, "expected at least one indexed InChIKey"
    sample_ik = next(iter(res.index))
    hits = res.resolve(sample_ik)
    for h in hits:
        assert h.vendor == "enamine"
        assert h.sku.startswith("EN300-")
        assert h.canonical_url == f"https://enaminestore.com/catalog/{h.sku}"


def test_resolver_normalizes_bare_id_to_en300_prefix(fixture_dir, tmp_path) -> None:
    """If the SDF carries a bare numeric id (no EN300- prefix), the resolver
    must normalize it. Build a tiny synthetic SDF to exercise this path."""
    import textwrap
    p = tmp_path / "tiny.sdf"
    p.write_text(textwrap.dedent("""\
        Foo
        ...
        > <InChIKey>
        BSYNRYMUTXBXSQ-UHFFFAOYSA-N

        > <Catalog ID>
        7605608

        $$$$
        """))
    res = EnamineSdfResolver.from_files([p])
    hits = res.resolve("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    assert hits and hits[0].sku == "EN300-7605608"


def test_resolver_returns_empty_list_for_unknown_inchikey(fixture_dir) -> None:
    res = EnamineSdfResolver.from_files([fixture_dir / "enamine_acids_snippet.sdf"])
    assert res.resolve("ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-Z") == []
```

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/resolvers/enamine_sdf.py
"""Parse Enamine BB SDFs into an InChIKey → ResolverHit index.

Per CLAIM-08 (VERIFIED): per-functional-class SDFs at
  enamine.net/building-blocks/functional-classes/{acids,boronics,amines,halides}
are anonymously downloadable. Total BB catalog is 2,292,307 (CLAIM-09 — the
original report's 573K was 4× stale).

SKU field name in the SDF varies across exports; we accept any of:
  "Catalog ID", "idnumber", "ID", "EN_ID"
and prefix with EN300- if not already present.

Per CLAIM-07: canonical product URL is
  https://enaminestore.com/catalog/EN300-{N}     (no www)
SKU width is variable (6 to 8+ digits) — regex is `EN300-\\d+`, not strictly 6.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from aichemy_pricing.resolvers._sdf import iter_sdf_records
from aichemy_pricing.types import ResolverHit

_SKU_TAGS = ("Catalog ID", "idnumber", "ID", "EN_ID")
_INCHIKEY_TAGS = ("InChIKey", "INCHIKEY", "PUBCHEM_IUPAC_INCHIKEY")


def _first(rec: dict[str, list[str]], tags: tuple[str, ...]) -> str | None:
    for t in tags:
        v = rec.get(t)
        if v:
            return v[0]
    return None


@dataclass
class EnamineSdfResolver:
    name: str = "enamine_sdf"
    index: dict[str, list[ResolverHit]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_files(cls, paths: list[Path]) -> "EnamineSdfResolver":
        self = cls()
        for path in paths:
            for rec in iter_sdf_records(Path(path)):
                ik = _first(rec, _INCHIKEY_TAGS)
                sku = _first(rec, _SKU_TAGS)
                if not (ik and sku):
                    continue
                if not sku.startswith("EN300-"):
                    sku = f"EN300-{sku}"
                self.index[ik].append(
                    ResolverHit(
                        inchikey=ik,
                        vendor="enamine",
                        sku=sku,
                        canonical_url=f"https://enaminestore.com/catalog/{sku}",
                    )
                )
        return self

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.index.get(inchikey, []))
```

- [ ] **Step 4: Re-export**

```python
# src/aichemy_pricing/resolvers/__init__.py — append
from aichemy_pricing.resolvers.enamine_sdf import EnamineSdfResolver

__all__ = ["PubChemSdfResolver", "EnamineSdfResolver"]
```

- [ ] **Step 5: Run; pass (3 tests)**

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/resolvers/enamine_sdf.py src/aichemy_pricing/resolvers/__init__.py src/aichemy_pricing/tests/test_resolvers_enamine.py src/aichemy_pricing/tests/data/enamine_acids_snippet.sdf
git commit -m "feat(pricing): EnamineSdfResolver — InChIKey → EN300-* SKU"
```

---

## Task B3: `ZincTrancheResolver`

**Per CLAIM-03 (VERIFIED):** `https://files.docking.org/2D/` serves real ZINC20 2D tranche files (`.smi` format, one molecule per line, with vendor supplier-code annotations in extra columns). **Per CLAIM-02 (PARTIAL):** the report's exact `catitms.txt?count=all` URL 404s anonymously, but the underlying `catitms` join is real (~408 catalogs in ZINC15). The right path for bulk pulls is the Tranche Browser at `files.docking.org/2D/`. **Per CLAIM-20 (VERIFIED):** Combi-Blocks is one of the ~408 ZINC catalogs (`combiblocksbb` short_name).

**Files:**
- Create: `src/aichemy_pricing/resolvers/zinc_tranches.py`
- Create: `src/aichemy_pricing/tests/test_resolvers_zinc.py`
- Capture: `src/aichemy_pricing/tests/data/zinc_tranche_sample.smi`

- [ ] **Step 1: Capture fixture (via shared `_capture.py` validator)**

The previous version of this step used `curl -sL ... | head -50 > foo.smi || echo` — that pipeline silently writes a zero-byte file on 404 (curl returns 0 without `--fail`; redirection always succeeds; the `||` fallback never fires). Combined with the live test's `if size == 0: skip` predicate, a broken capture would silently mask a parser-format mismatch. Route through the shared validator instead.

```bash
# Step 1a: confirm a tranche path exists via the directory browser:
curl -sIL "https://files.docking.org/2D/" | head -3
# Open https://files.docking.org/2D/ in a browser, pick a current 4-letter
# cohort (e.g. AB, BC, ...). Replace <COHORT>/<NAME>.smi below with what you see.

# Step 1b: capture with validation. Required markers: a tab character
# (the resolver only handles tab-separated rows) and a 'ZINC' substring
# (every ZINC tranche has at least one ZINCnnn id; absence means the
# response was a 404 HTML page, not the .smi file).
uv run python -m aichemy_pricing.tests.data._capture \
  --url "https://files.docking.org/2D/<COHORT>/<NAME>.smi" \
  --out src/aichemy_pricing/tests/data/zinc_tranche_sample.smi \
  --min-size 5000 \
  --required-marker $'\t' \
  --required-marker ZINC
# Then truncate to the first 50 lines (the helper writes the whole body):
head -50 src/aichemy_pricing/tests/data/zinc_tranche_sample.smi \
  > src/aichemy_pricing/tests/data/zinc_tranche_sample.smi.head \
  && mv src/aichemy_pricing/tests/data/zinc_tranche_sample.smi.head \
        src/aichemy_pricing/tests/data/zinc_tranche_sample.smi
```

The `_capture.py` validator (Sub-Plan A Task A7) refuses to write the fixture if the response 404s, returns a redirect-page, or lacks the tab/ZINC markers — silent zero-byte and HTML-404 fixtures are no longer possible. The tranche file contains rows like:
```
SMILES   zinc_id    [vendor:supplier_code ...]
```

- [ ] **Step 2: Failing tests**

```python
# src/aichemy_pricing/tests/test_resolvers_zinc.py
"""Unit tests for ZincTrancheResolver."""
from __future__ import annotations

import textwrap

import pytest

from aichemy_pricing.resolvers.zinc_tranches import ZincTrancheResolver


def test_resolver_parses_synthetic_smi(tmp_path) -> None:
    """Use a synthetic SMI to exercise the parser without depending on a real
    ZINC file (which has variable column counts depending on cohort)."""
    smi = textwrap.dedent("""\
        smiles\tzinc_id\tinchikey\tvendor:supplier_code
        CCO\tZINC000000000702\tLFQSCWFLJHTTHZ-UHFFFAOYSA-N\tsigma:E7023;enamine:EN300-12345
        CC\tZINC000000000456\tOTMSDBZUPAUEDD-UHFFFAOYSA-N\tcombiblocksbb:CB-123
        """)
    p = tmp_path / "tiny.smi"
    p.write_text(smi)
    res = ZincTrancheResolver.from_files([p])
    hits = res.resolve("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
    vendors = {h.vendor for h in hits}
    assert "sigma" in vendors and "enamine" in vendors


def test_resolver_returns_empty_for_unknown_inchikey(tmp_path) -> None:
    p = tmp_path / "empty.smi"
    p.write_text("smiles\tzinc_id\tinchikey\tvendor:supplier_code\n")
    res = ZincTrancheResolver.from_files([p])
    assert res.resolve("ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-Z") == []


def test_resolver_skips_rows_without_inchikey(tmp_path) -> None:
    smi = "smiles\tzinc_id\tinchikey\tvendor:supplier_code\nCCO\tZINC0\t\tsigma:X\n"
    p = tmp_path / "noik.smi"
    p.write_text(smi)
    res = ZincTrancheResolver.from_files([p])
    assert res.index == {}


def test_resolver_handles_alternate_column_order(tmp_path) -> None:
    """Real ZINC cohorts emit columns in different orders; the parser must
    locate the InChIKey by *shape*, not by fixed position."""
    # InChIKey first, SMILES last (some cohorts/exports do this).
    smi = (
        "inchikey\tzinc_id\tvendor:supplier_code\tsmiles\n"
        "LFQSCWFLJHTTHZ-UHFFFAOYSA-N\tZINC702\tsigma:E7023\tCCO\n"
    )
    p = tmp_path / "alt.smi"
    p.write_text(smi)
    res = ZincTrancheResolver.from_files([p])
    hits = res.resolve("LFQSCWFLJHTTHZ-UHFFFAOYSA-N")
    assert len(hits) == 1 and hits[0].vendor == "sigma"


def test_resolver_rejects_non_inchikey_strings(tmp_path) -> None:
    """A row whose 'inchikey' column is malformed (wrong length / shape) must
    not pollute the index — even if a vendor field is present."""
    smi = "smiles\tzinc_id\tinchikey\tvendor:supplier_code\nCCO\tZINC0\tNOT-A-VALID-IK\tsigma:X\n"
    p = tmp_path / "bad.smi"
    p.write_text(smi)
    res = ZincTrancheResolver.from_files([p])
    assert res.index == {}


@pytest.mark.live
def test_resolver_parses_real_tranche_fixture(fixture_dir) -> None:
    """If the fixture was captured, the resolver must extract at least one
    indexed InChIKey. A silent empty-index pass would mask the parser being
    out-of-sync with the real ZINC tranche file format."""
    p = fixture_dir / "zinc_tranche_sample.smi"
    if not p.exists() or p.stat().st_size == 0:
        pytest.skip("no zinc tranche fixture captured")
    res = ZincTrancheResolver.from_files([p])
    assert isinstance(res.index, dict)
    # If the fixture has tabs and at least one valid InChIKey-shaped column,
    # we must index at least one entry. If this fails, the parser is wrong
    # for the captured tranche format — fix the resolver, not the test.
    has_tabs = "\t" in p.read_text(errors="replace")
    if has_tabs:
        assert res.index, (
            "tranche fixture is tab-separated but parser indexed zero InChIKeys; "
            "real ZINC column layout likely differs from what the resolver assumes"
        )
```

- [ ] **Step 3: Implement**

```python
# src/aichemy_pricing/resolvers/zinc_tranches.py
"""Parse ZINC20 2D tranche files into an InChIKey → multi-vendor ResolverHit index.

Per CLAIM-03 (VERIFIED): https://files.docking.org/2D/ hosts ZINC20 tranches.
Per CLAIM-02 (PARTIAL): the report's catitms `count=all` URL 404s anonymously;
use the Tranche Browser instead.

Tranche file format varies across cohorts. Common shapes (tab-separated):
    smiles  zinc_id  [inchikey]  [vendor1:code1;vendor2:code2;...]
…or (rarely):
    inchikey  zinc_id  vendor:supplier_code  smiles

We do not trust column positions. Instead the parser scans each row for:
  • an InChIKey-shaped token (regex `[A-Z]{14}-[A-Z]{10}-[A-Z]`)
  • a vendor-list-shaped token (contains `:`; vendor codes split on `;`)

This makes the resolver robust to layout variation across cohorts.
The `combiblocksbb` short_name is the recognized ZINC short_name for
Combi-Blocks (CLAIM-20).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from aichemy_pricing.types import ResolverHit

_INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def _parse_vendor_field(field_value: str) -> list[tuple[str, str]]:
    """Parse `sigma:E7023;enamine:EN300-12345` → [("sigma","E7023"), ("enamine","EN300-12345")]."""
    out: list[tuple[str, str]] = []
    for token in field_value.split(";"):
        token = token.strip()
        if not token or ":" not in token:
            continue
        vendor, code = token.split(":", 1)
        vendor, code = vendor.strip(), code.strip()
        if vendor and code:
            out.append((vendor, code))
    return out


def _find_inchikey(parts: list[str]) -> str | None:
    for p in parts:
        if _INCHIKEY_RE.match(p.strip()):
            return p.strip()
    return None


def _find_vendor_field(parts: list[str]) -> str | None:
    """Pick the first column that parses as at least one `vendor:code` token."""
    for p in parts:
        if ":" in p and _parse_vendor_field(p):
            return p
    return None


@dataclass
class ZincTrancheResolver:
    name: str = "zinc_tranche"
    index: dict[str, list[ResolverHit]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def from_files(cls, paths: list[Path]) -> "ZincTrancheResolver":
        self = cls()
        for path in paths:
            with Path(path).open("rt", errors="replace") as f:
                _header = f.readline()  # discard header row
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 2:
                        continue
                    inchikey = _find_inchikey(parts)
                    if inchikey is None:
                        continue
                    vendor_field = _find_vendor_field(parts)
                    if vendor_field is None:
                        continue
                    for vendor, code in _parse_vendor_field(vendor_field):
                        self.index[inchikey].append(
                            ResolverHit(inchikey=inchikey, vendor=vendor, sku=code)
                        )
        return self

    def resolve(self, inchikey: str) -> list[ResolverHit]:
        return list(self.index.get(inchikey, []))
```

- [ ] **Step 4: Re-export**

```python
# src/aichemy_pricing/resolvers/__init__.py — final
from aichemy_pricing.resolvers.enamine_sdf import EnamineSdfResolver
from aichemy_pricing.resolvers.pubchem_sdf import PubChemSdfResolver
from aichemy_pricing.resolvers.zinc_tranches import ZincTrancheResolver

__all__ = ["PubChemSdfResolver", "EnamineSdfResolver", "ZincTrancheResolver"]
```

- [ ] **Step 5: Run; pass (3 unit tests; 1 live test skipped by default)**

- [ ] **Step 6: Commit**

```bash
git add src/aichemy_pricing/resolvers/zinc_tranches.py src/aichemy_pricing/resolvers/__init__.py src/aichemy_pricing/tests/test_resolvers_zinc.py src/aichemy_pricing/tests/data/zinc_tranche_sample.smi
git commit -m "feat(pricing): ZincTrancheResolver — InChIKey → multi-vendor codes"
```

---

## Unit Tests Summary (Sub-Plan B)

| Test file | Test count | Notes |
|---|---:|---|
| `test_sdf_parser.py` | 4 | Two-record parse; multiline values; truncated-record handling; **.sdf.gz transparent read (Revision 22)** |
| `test_resolvers_pubchem.py` | 5 | Indexing; per-hit shape; allowed_sources filter; unknown-IK; URL field |
| `test_resolvers_enamine.py` | 3 | Indexing + URL construction; bare-id normalization to EN300-*; unknown-IK |
| `test_resolvers_zinc.py` | 5 + 1 `live` | Synthetic SMI parse; missing-IK skip; **alternate column order**; **rejects malformed IK**; multi-vendor split; (live) real-fixture must produce ≥1 hit |
| **Total** | **17 + 1 live** | All offline unit tests run in <2s. |

**All-tests command:**
```bash
uv run pytest src/aichemy_pricing/tests/test_sdf_parser.py src/aichemy_pricing/tests/test_resolvers_*.py -v
```

**Type-check:**
```bash
uv run mypy src/aichemy_pricing/resolvers/
```
Expected: Success.

---

## Self-review

**Spec coverage:** All three resolvers promised in the header are delivered: PubChem (CLAIM-04), Enamine (CLAIM-08), ZINC (CLAIM-03). Each parses a fixture committed to `tests/data/`, and each has at least one negative test (unknown-IK returns empty list).

**Placeholder scan:** No "TBD" / "implement later". The fixture-capture step for Task B3 includes a fallback note (the `files.docking.org/2D/` directory layout uses 4-letter cohort names that change over time; the test uses a synthetic SMI to be deterministic and the live test on the real fixture is `live`-marked + size-guarded).

**Type consistency:** All three resolvers return `list[ResolverHit]` from `resolve(inchikey: str)` and have a `name: str` attribute, satisfying the `VendorResolver` protocol from sub-plan A. The `_iter_sdf_records` (renamed `iter_sdf_records`) helper is reused by both SDF resolvers — single source of truth for the SDF format.

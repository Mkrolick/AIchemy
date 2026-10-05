# `aichemy-pricing` — Standalone Vendor Price-Scraping Package (Master Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Sub-plans (each independently reviewable / executable)

This master plan is broken into 5 self-contained sub-plans. Each can be reviewed (e.g., via `/ultrareview <file>`) and executed independently of the others, subject to the listed dependencies.

| Sub-plan | File | Depends on | Tests (offline + live) |
|---|---|---|---:|
| **A** Foundation | [`2026-04-25-aichemy-pricing-A-foundation.md`](./2026-04-25-aichemy-pricing-A-foundation.md) | — | 21 + 0 |
| **B** Offline resolvers | [`2026-04-25-aichemy-pricing-B-resolvers.md`](./2026-04-25-aichemy-pricing-B-resolvers.md) | A | 17 + 1 |
| **C** Tier 1 vendors (L2: Fluorochem, Tocris, Molbase) | [`2026-04-25-aichemy-pricing-C-tier1-vendors.md`](./2026-04-25-aichemy-pricing-C-tier1-vendors.md) | A | 15 + 3 |
| **D** Tier 3 vendor (L2: MedChemExpress only) | [`2026-04-25-aichemy-pricing-D-tier2-3-vendors.md`](./2026-04-25-aichemy-pricing-D-tier2-3-vendors.md) | A (parallel with B/C/F) | 4 + 1 |
| **F** Browserbase L3 fallback (Sigma, Enamine, Cayman, ChemCruz, Tocris fb, Molbase fb) | [`2026-04-25-aichemy-pricing-F-browserbase-l3.md`](./2026-04-25-aichemy-pricing-F-browserbase-l3.md) | A (parallel with B/C/D) | 21 + 0 |
| **E** CLI + integration | [`2026-04-25-aichemy-pricing-E-cli-integration.md`](./2026-04-25-aichemy-pricing-E-cli-integration.md) | A, B, C, D, F | 14 + 0 |
| **Total** | | | **92 + 5** |

**Recommended execution DAG:**
- A first.
- B, C, D in parallel after A (they touch disjoint files).
- E last (consumes all prior).

The remainder of this document is the **architectural overview** the sub-plans reference. Implementation details live in the sub-plan files.

---

**Goal:** Build `aichemy-pricing`, a standalone Python package (importable, CLI-runnable, independently testable) that resolves a chemical identifier (InChIKey / SMILES / CAS) to a per-gram USD price via a tiered chain of verified vendor sources, then plug it into the AIchemy pipeline as a thin import.

**Architecture:** Sibling package at `src/aichemy_pricing/` with its own `pyproject.toml` extras + console script + standalone pytest suite. **Three-tier lookup, single-chain composition:**
- **L1 (cache):** `CachedPriceLookup` over SQLite. Hits free, instant.
- **L2 (httpx):** Direct HTTPS to vendor APIs. Free, ~100 ms/lookup. Members: Fluorochem (Azure-blob JSON, no auth), Tocris + Molbase (SSR HTML), MedChemExpress (`curl_cffi` for Cloudflare).
- **L3 (Browserbase Fetch API):** One POST → rendered markdown → vendor-specific markdown parser. ~$0.001/page, ~5 s/page. Covers Sigma-Aldrich (Akamai-gated → Browserbase stealth), Enamine, Cayman, ChemCruz, plus Tocris/Molbase fallback. Browser API + LLM extraction reserved as `NotImplementedError` stubs for future revisions.
- **Offline-catalog resolvers** (Sub-Plan B): JOIN InChIKey → vendor SKU using PubChem FTP / ZINC tranches / Enamine BB SDFs (zero scraping). Drives the chain.

Every URL/schema fact is anchored to a `CLAIM-XX` verdict in `experiments/chem-pricing-verification/`.

**Tech Stack:** Python 3.11+, `httpx`, `curl_cffi` (Cloudflare bypass), `polars`, `pydantic` v2, `typer` (CLI), `pytest` + `pytest-httpx` (replay tests), `uv` for builds. **Browserbase Fetch API** as L3 — one HTTPS POST per page, no Playwright/CDP. The Browser API + LLM-extraction paths are stubbed (`NotImplementedError` with a clear message) so a future revision can swap them in without re-architecting.

**Verified facts driving this plan:** see `experiments/chem-pricing-verification/VERIFICATION.md` (29/29 claims with verdicts) and per-claim evidence in `experiments/chem-pricing-verification/evidence/CLAIM-*.md`. Verdict tally: 18 VERIFIED, 8 PARTIAL (specifics need correction), 1 FALSIFIED (Apollo — drop entirely), 2 PLAUSIBLE estimates. Apollo Scientific is **omitted** from this plan because its e-commerce surface no longer exists (CLAIM-11). Sigma-Aldrich and TCI are **deferred to a future Tier 4 plan** because they require residential proxies + WAF-aware infrastructure (CLAIM-12, CLAIM-13).

---

## File Structure

```
src/aichemy_pricing/                       # NEW — sibling package, no aichemy.* imports
├── __init__.py                            # public API: lookup, lookup_batch, VendorChain
├── _version.py                            # __version__
├── types.py                               # PriceQuote, VendorRef, ResolverHit (pydantic)
├── protocol.py                            # PriceLookup, VendorResolver protocols
├── chain.py                               # ChainedPriceLookup, CachedPriceLookup (SQLite)
├── ratelimit.py                           # token-bucket rate limiter
├── http.py                                # shared httpx.Client factory + curl_cffi factory
│
├── resolvers/                             # Offline InChIKey → vendor-SKU JOINs
│   ├── __init__.py
│   ├── pubchem_sdf.py                     # parses PubChem Substance SDF FTP dump
│   ├── enamine_sdf.py                     # parses Enamine BB SDFs per functional class
│   └── zinc_tranches.py                   # parses ZINC20 2D tranche files
│
├── vendors/                               # One module per vendor; all stateless
│   ├── __init__.py
│   ├── fluorochem.py                      # Tier 1: Azure-blob JSON pricing API
│   ├── molbase.py                         # Tier 1: /cas/{CAS}.html
│   ├── tocris.py                          # Tier 1: /products/{slug}_{id}
│   ├── enamine.py                         # Tier 2: discovered XHR JSON endpoint
│   ├── cayman.py                          # Tier 2: SSR title + XHR price
│   ├── chemcruz.py                        # Tier 2: /p/{slug}-{cas}
│   └── medchemexpress.py                  # Tier 3: curl_cffi for Cloudflare
│
├── cli.py                                 # `aichemy-price` console script
└── py.typed                               # PEP 561 marker

src/aichemy_pricing/tests/                 # standalone test suite; runs without aichemy
├── conftest.py                            # fixtures: tmp cache, fake httpx responses
├── test_chain.py
├── test_cache.py
├── test_resolvers_pubchem.py
├── test_resolvers_enamine.py
├── test_vendors_fluorochem.py             # replay tests + 1 live-marked test
├── test_vendors_molbase.py
├── test_vendors_tocris.py
├── test_vendors_enamine.py
├── test_vendors_cayman.py
├── test_vendors_chemcruz.py
├── test_vendors_medchemexpress.py
├── test_cli.py
└── data/                                  # frozen replay JSON / HTML fixtures (small)
    ├── fluorochem_F765353.json            # captured live during CLAIM-01
    ├── molbase_aspirin.html
    ├── tocris_jw642.html
    └── ...

pyproject.toml                             # MODIFIED — add `pricing` extra + entry point
src/aichemy/preprocessing/augment/prices.py  # MODIFIED — replace bespoke scrapers with `from aichemy_pricing import ...`
```

**Key boundary:** `aichemy_pricing` does **not** import anything from `aichemy.*`. The reverse arrow (aichemy → aichemy_pricing) is fine and is the only integration point. This means `pytest src/aichemy_pricing/tests/` runs without the rest of the project.

---

## Implementation phases — see sub-plans for full TDD task lists

Phase content has been moved to the dedicated sub-plan files (see Sub-plans table at top). The master plan keeps only the architectural overview to avoid drift between two copies of the same task list. Each sub-plan is fully self-contained.

| Phase | Sub-plan | Summary |
|---|---|---|
| 0 — Package scaffolding | A | Add `pricing` extra + console script; create package skeleton + test harness; extend hatch/mypy/pytest scopes (Revision 24) |
| 1 — Core types/chain/cache | A | `types.py`, `protocol.py`, `ratelimit.py`, `chain.py` (with R17 try/except guard), `http.py`; SQLite-backed quote cache |
| 2 — Offline catalog resolvers | B | PubChem SDF (gzip-aware per R22), Enamine BB SDF, ZINC tranche resolvers (column-agnostic per R5) |
| 3 — Tier 1 L2 vendors (plain HTTP) | C | Fluorochem (Azure-blob JSON), Molbase (CNY support per R3), Tocris (MW-strip per R18) |
| 4 — Tier 3 L2 vendor (Cloudflare) | D | MedChemExpress only (`curl_cffi`); Enamine/Cayman/ChemCruz moved to Sub-Plan F |
| 5 — L3 Browserbase Fetch fallback | F | One-POST fetch_markdown client; per-vendor markdown parsers (Sigma, Enamine, Cayman, ChemCruz, Tocris, Molbase); Browser API + LLM as stubs |
| 6 — CLI | E | `aichemy-price` Typer app with `lookup`, `chain`, `resolve` |
| 7 — Public API + AIchemy integration | E | `__init__.py` re-exports; `PricesConfig` schema update (R23); `_InchikeyAdapter` with FX-staleness warning (R28); `make_lookup` branch |
| 8 — End-to-end verification | E | Standalone test suite, AIchemy regression, README, run on 100K-compound subset |

## Going-live checklist (deliberately deferred items)

Items intentionally **not** in this plan because they need more infrastructure than the standalone package should depend on:

- **Sigma-Aldrich.** Akamai-gated (CLAIM-13). **Now in scope via Sub-Plan F's L3 path** — Browserbase's stealth + residential IPs handle Akamai for the Fetch API. If Browserbase 403s on Sigma at scale (it sometimes does), fall back to deferring Sigma; L1+L2 still produces partial coverage.
- **TCI Chemicals.** Akamai-gated (CLAIM-12). Same situation as Sigma — deferred unless Sub-Plan F's L3 path proves reliable for Akamai vendors. Add a `tci.py` markdown parser to `aichemy_pricing.browserbase.parsers/` if it does.
- **Apollo Scientific.** FALSIFIED (CLAIM-11) — store decommissioned. Permanently excluded.
- **BLDpharm.** URL pattern in original report is wrong (CLAIM-16); real pattern not yet discovered. Mark TODO; not worth pursuing until a working URL example is sourced.
- **Browser API + LLM extraction (Sub-Plan F stubs).** Reserved module names that raise `NotImplementedError` in v1. Build only when (a) a vendor needs multi-step browser interaction beyond a single Fetch call, or (b) the per-vendor regex parser cost grows past LLM-call cost (~50+ vendors).
- **Avanti SAP migration (June 2026).** Per CLAIM-21, MilliporeSigma will change Avanti SKU codes in June 2026. Cache TTL of 30 days mitigates this; full re-resolution recommended after the migration window.

---

## Self-review

**Spec coverage check:** Every verdict in `experiments/chem-pricing-verification/CLAIMS.md` is reflected in this plan: VERIFIED claims become implementation tasks; PARTIAL claims become implementation tasks with explicit "use the corrected URL/schema" notes; FALSIFIED (Apollo) is explicitly excluded; quantitative estimates inform the going-live yield expectations rather than the implementation. The two deliberately-deferred buckets (Sigma/TCI, BLD) are documented above.

**Placeholder scan:** No "TBD" / "implement later" — every code step has actual code. Discovery actions for Tier 2 (Tasks 4.1–4.3) and Tier 3 (Task 5.1) are explicit one-time manual steps, not placeholders. Task 2.3 (ZINC tranches) reuses the SDF parser pattern from 2.1/2.2 — the implementation reference is the prior task, which is the convention this codebase already uses.

**Type consistency:** `VendorRef`, `ResolverHit`, `PriceQuote` are used consistently across all vendor modules and resolvers. The `lookup(ref: VendorRef) -> PriceQuote | None` signature is the single mental model.

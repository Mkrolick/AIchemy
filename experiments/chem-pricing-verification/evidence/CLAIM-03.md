# CLAIM-03 — ZINC 2D tranche files + ZINC-22 cartblanche

**Status:** VERIFIED

**Claim:** `http://files.docking.org/2D/` hosts the ZINC 2D tranche files; `cartblanche22.docking.org` hosts ZINC-22.

## Verification steps performed

- [iter 3] curl `http://files.docking.org/2D/` → 301 → `https://files.docking.org/2D/` → returns real "Index of /2D" Apache directory listing titled **"Welcome to ZINC20 2D Tranches for Download!"** with full documentation of the 4D tranche schema (MW × logP × reactivity × purchasability, 121 first-level tranches).
- [iter 3] curl `https://cartblanche22.docking.org/` → **200 OK**, `Content-Disposition: inline; filename=index.html`, served by gunicorn.
- [iter 3] curl `https://cartblanche.docking.org/` → also 200 OK (same service).
- [iter 3] WebSearch corroboration:
  - GitHub repo [`docking-org/cartblanche22`](https://github.com/docking-org/cartblanche22) — official "A molecule shopping cart and ZINC-22 search tool".
  - DISI wiki [Zinc22:Searching](https://wiki.docking.org/index.php/Zinc22:Searching) page documents the search interface.
  - [ZINC-22 paper](https://pubs.acs.org/doi/10.1021/acs.jcim.2c01253) (Tingle et al., JCIM 2023) cites cartblanche22.

## Evidence

### `files.docking.org/2D/` HTML excerpt (verbatim)

```
Index of /2D
Welcome to ZINC20 2D Tranches for Download!
About: This area contains static exports of 2D physical property subsets to support the tranche browser.
It is refreshed every 60 days (each file is timestamped). Supported by NIH GM71896 to JJI.
...
Physico-chemical property space is organized in 2D into 121 first-level tranches and two further dimensions...
Use the Tranche Browser at http://wiki.docking.org/index.php/Tranche_Browser to facilitate downloading these files.
```

### Headers

- `files.docking.org`: `Server: Apache/2.4.37 (Rocky Linux)`, anonymous read.
- `cartblanche22.docking.org`: `Server: gunicorn`, anonymous read.

### Caveat

Subdomain `files2.docking.org/2D/` returned 403 — the report didn't claim files2 but a ResearchGate post had suggested it as an alternative; it is now restricted.

## Verdict

**VERIFIED.** Both URLs are live and serve the content the report claims. Note that `files.docking.org/2D/` is labelled "ZINC20" (the canonical tranche export namespace), so a scraper using this for the "ZINC 2D tranches" intent of the report is correct. License caveat embedded in the index: ZINC redistribution requires John Irwin's explicit written permission — fine for internal use, blocks redistribution of bulk dumps.

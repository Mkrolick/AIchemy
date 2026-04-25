# CLAIM-02 — ZINC catitms bulk dump

**Status:** PARTIAL

**Claim:** `https://zinc15.docking.org/catitms.txt:catalog.short_name,catitm.supplier_code,substance.zinc_id,substance.smiles?count=all` returns supplier codes for **310 catalogs across ~150 vendors for ~1.3 billion compounds**.

## Verification steps performed

- [iter 2] curl exact URL from report → **HTTP/2 404** (Server: gunicorn/19.3.0).
- [iter 2] curl variants:
  - `catitms.txt?count=1` → 404
  - `catitms.txt:catalog.short_name+catitm.supplier_code?count=10` → 404
  - `catitms.txt:catalog.short_name,catitm.supplier_code,substance.zinc_id,substance.smiles?count=10` → 404
  - `catalogs/sigma/catitms.txt?count=5` → returns "ZINC Error" HTML page
  - `catalogs.txt` → 200 (root catalogs endpoint exists)
  - `catalogs.txt:short_name?count=all` → 200, **409 lines** (≈408 catalogs after header)
  - `substances.txt:zinc_id?count=1` → returns `ZINC000915973095` (proves the `.txt:fields?params` URL syntax IS real, just not the multi-field catitms variant under anonymous access)
- [iter 2] WebFetch `wiki.docking.org/index.php/ZINC15:examples:public` — confirms the canonical URL pattern syntax (the report's URL template is consistent with the wiki). Wiki recommends adding `&catalog.np=1` filter for "now-purchasable" filtering.
- [iter 2] WebSearch for ZINC15 size:
  - PubMed-Central / 2015 ACS JCIM paper: ZINC15 contains "over 120 million purchasable drug-like compounds" / "over 230 million purchasable compounds in ready-to-dock, 3D formats" ([Sterling & Irwin, JCIM 2015](https://pubs.acs.org/doi/10.1021/acs.jcim.5b00559)).
  - "1.3 billion" matches **ZINC22**, not ZINC15 ([Tingle et al., ZINC-22, JCIM 2023](https://pubs.acs.org/doi/10.1021/acs.jcim.2c01253)). ZINC22 is hosted at `cartblanche22.docking.org`, not `zinc15.docking.org`.

## Evidence

- Canonical ZINC15 catalog count = **~408 catalogs** (`catalogs.txt:short_name?count=all` returned 409 lines including header). Report's "310 catalogs" is in the right ballpark but not exact; "150+ vendors" is plausible because multiple catalogs (e.g., several per Sigma brand) map to one vendor.
- ZINC15 size: **120M–230M compounds**, not 1.3B. The 1.3B figure is **ZINC22**, a *different* database at a different URL.
- The full-form catitms URL with `count=all` from anonymous IP is **rate-limited / 404'd** in 2026. Wiki indicates serious bulk pulls should use the Tranche Browser (`http://files.docking.org/2D/`) or, for the multi-billion modern set, ZINC22 / `cartblanche22.docking.org`.

## Verdict

**PARTIAL.** The URL pattern syntax is real and documented; ZINC's `catitms` concept (catalog + supplier_code + zinc_id + smiles join) genuinely exists and ~408 catalogs are listed, so the architectural premise (offline InChIKey → vendor catalog ID join) survives. But two specifics are wrong:
1. **"1.3 billion compounds" is a confusion of ZINC15 with ZINC22.** ZINC15 is ~120–230M; the 1.3B figure belongs to ZINC22 at `cartblanche22.docking.org`. A scraper following the report's URL would get at most ZINC15's 230M coverage.
2. **The exact URL the report gives 404s** under anonymous access in 2026. Bulk pulls should use the Tranche Browser at `files.docking.org/2D/` or migrate to ZINC22; per-catalog `catitms.txt` queries also need authenticated access for full pulls.

The strategic recommendation (offline join, then targeted price scrapes) is sound; the tactical URL needs replacement with either a Tranche download or a ZINC22 query.

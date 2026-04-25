# Chemical Pricing Vendor Scraping — VERIFICATION (annotated)

**Verification status:** COMPLETE — 29/29 atomic claims have a final verdict after 29 ralph-loop iterations of live HTTP probes + WebSearch corroboration.

## Top-line summary

| Bucket | Count | Claim IDs |
|---|---:|---|
| **VERIFIED** (with or without minor notes) | 18 | 03, 05, 06, 07, 08, 10, 13, 14, 15, 17, 19, 20, 21, 22, 23, 24, 26, 27 |
| **PARTIAL** (capability real but specifics wrong) | 8 | 01, 02, 04, 09, 12, 16, 18, 25 |
| **FALSIFIED** (substantively wrong) | 1 | 11 (Apollo Scientific) |
| **PLAUSIBLE** (estimate, no live verdict) | 2 | 28 (USPTO yield, optimistic), 29 (MetanetX yield, well-calibrated) |

## What survived (VERIFIED — use as written)

- **CLAIM-03 — ZINC tranche files + cartblanche22:** `files.docking.org/2D/` + `cartblanche22.docking.org` both live; ZINC20 tranche schema documented in directory listing.
- **CLAIM-05 — PubChem PUG-REST rate limits (5 req/s, 400 req/min):** exact match to NIH docs. Plus a third undocumented-by-report cap of 300 s running-time per minute.
- **CLAIM-06 — PUG-REST endpoint shapes:** all three URL templates work on aspirin (CID 2244, InChIKey BSYNRYMUTXBXSQ-UHFFFAOYSA-N).
- **CLAIM-07 — Enamine Store URL `/catalog/EN300-{N}`:** verified live (use `EN300-\d+`, not strictly 6 digits; canonical host `enaminestore.com` no www).
- **CLAIM-08 — Enamine BB SDF downloads:** per-functional-class SDFs at `/building-blocks/functional-classes/{acids,boronics,amines,halides}` — anonymous download.
- **CLAIM-10 — Enamine screening collections (HTS 1.96M / Advanced 752k / Premium 72k):** all three numbers exact match.
- **CLAIM-13 — Sigma-Aldrich URL pattern + Akamai:** verified, but `combiblocksinc` brand prefix is suspect (Combi-Blocks is independent of Merck) and brand list is non-exhaustive (also `enamine`, `usp`).
- **CLAIM-14 — Cayman Chemical URL `/product/{itemID}/{slug}`:** verified, but **"sequential / enumerable" is misleading** — IDs are non-contiguous across multiple ranges; drive scraper from sitemap not `range(1, 25000)`.
- **CLAIM-15 — MedChemExpress `.html` slug + Cloudflare 403:** every specific exact match (URL, slug suffix, all four CoA salt forms, CF gating, browser-UA-insufficient).
- **CLAIM-17 — Santa Cruz / ChemCruz `/p/{slug}-{cas}` + 175,000 biochemicals:** verbatim match to vendor copy.
- **CLAIM-19 — Molport API 10K req/month free tier:** exact match. Note: directory page shows ~59 visible suppliers, marketing copy says "hundreds" — "100+" is loose.
- **CLAIM-20 — Combi-Blocks SDF + ZINC ingestion:** confirmed `combiblocksbb` short_name in zinc15.docking.org/catalogs.txt.
- **CLAIM-21 — Avanti redirect to avantiresearch.com:** verified live; bonus warning — Avanti SKU codes change June 2026 due to MilliporeSigma SAP migration; re-resolve mappings then.
- **CLAIM-22 — Larodan ~3,000 lipids / EUR / structured code:** all three components verified.
- **CLAIM-23 — Login-walled vendor list:** verified by spot-check (TRC, AAblocks, Hit2Lead, Biosynth, Ambeed); Fisher implied; AstaTech/Bidepharm/Life Chemicals not probed but consistent with cohort.
- **CLAIM-24 — Quote-only vendor list:** verified by spot-check (Matrix "Inquire", BOC "inquir" ×7); others not probed but consistent.
- **CLAIM-26 — ChemSpider RSC key + redistribution prohibited:** verified. Bonus: free quota is only 1,000 calls/month — even tighter than PubChem.
- **CLAIM-27 — eMolecules requires login for pricing:** verified; "institutional" qualifier slightly overspecified (effectively any-registered B2B).

## What broke (PARTIAL — fix before using)

- **CLAIM-01 (Fluorochem Azure-blob JSON):** ✅ endpoint + anonymous access + pack-size variants are real. ❌ JSON shape was **fabricated** — actual schema uses `{Code:{Code-Pack:{SKU,Size,Size Unit,Pricing:{GBP:{Base Price, X% Discount, Q<N> <YYYY> - tier, Oxford - 15%, …}, EUR:{…}}}}}`. **No `min_gbp`/`max_gbp`/`has_stock_*` keys.** Stock data is not in this endpoint. Only modern F-prefix / BR-prefix SKUs resolve; legacy 6-digit codes 404. Container listing disabled.
- **CLAIM-02 (ZINC catitms URL):** ✅ URL syntax + `catitms` concept + ~408 catalogs (vs claimed 310) are real. ❌ "1.3B compounds" **conflates ZINC15 (~120–230M) with ZINC22 (multi-billion)** — different databases. Exact `count=all` URL 404s in 2026 — use Tranche Browser at `files.docking.org/2D/` or migrate to ZINC22 (`cartblanche22.docking.org`).
- **CLAIM-04 (PubChem Substance SDF FTP):** ✅ dump real, fresh, ~491M SIDs across 982 files. ❌ Actual SDF tag names are **`PUBCHEM_EXT_DATASOURCE_NAME` / `PUBCHEM_EXT_DATASOURCE_REGID`** (not "SourceName"/"RegistryID" verbatim). ❌ Total sources = **914**, vendor-tagged = **531** (231 active + 300 legacy) — **not "~700 vendor sources"**.
- **CLAIM-09 (Enamine BB catalog 573K):** ✅ "300,000 in stock" exact match. ❌ Total catalog is **2,292,307** — **off by ~4×**, looks like stale ~2018 figure.
- **CLAIM-12 (TCI URL + "light anti-bot"):** ✅ URL `/{REGION}/{lang}/p/{letter+4digits}` correct (V0058, P0147 confirmed). ❌ TCI is on **Akamai (`server: AkamaiGHost`)** — same heavy WAF as Sigma, not "light".
- **CLAIM-16 (Ambeed/BLD CAS URLs):** ✅ Ambeed `/products/{CAS}.html` verified, login-walled. ❌ **BLDpharm `/products/{CAS}.html` returns 404** — actual URL pattern not discovered; mark TODO.
- **CLAIM-18 (Molbase URL):** ✅ 49,406,656 compounds exact (matches "~49M"); anonymous prices visible. ❌ URL form wrong: actual is **`molbase.com/cas/{CAS}.html`** (no `/en/`, slash not hyphen) — report's `/en/cas-{CAS}.html` 404s 100%.
- **CLAIM-25 (Public-price vendor list):** 7/10 confirmed truly public; ⚠️ Sigma's "anon US" weakening; ⚠️ TCI's "public" misleading because Akamai blocks; **❌ Apollo wrongly included**.

## What's wholly false (FALSIFIED — drop entirely)

- **CLAIM-11 — Apollo Scientific:** Multiple errors:
  1. **Apollo and Fluorochem are NOT under common ownership** — Apollo is part of Central Glass Group (Japan, 33% acquired 2003); Fluorochem is an independent UK competitor. The "common ownership" framing is hallucinated.
  2. **`store.apolloscientific.co.uk` decommissioned** — 302-redirects to a WordPress marketing site with no e-commerce.
  3. `/product/{slug}` URL pattern returns 404.
  4. AWS WAF returned 403 to default-UA curl on the (defunct) store subdomain — "no anti-bot" claim also wrong.
  ⇒ **Drop Apollo from the scrape plan entirely.**

## Quantitative estimates (no live verdict)

- **CLAIM-28 — USPTO yield 600K–800K priced (50–70% hit rate):** PLAUSIBLE-OPTIMISTIC. Report's own internal math was inconsistent (claimed 600K–800K hits against 573K assumed BB catalog — impossible). Only physically feasible because real Enamine BB is 2.29M (CLAIM-09). 50–70% direct-match rate is at upper end of literature. **Revised estimate: 360K–600K priced compounds (30–50% hit rate × 1.2M)**.
- **CLAIM-29 — MetanetX yield 30K–80K priced:** PLAUSIBLE — well-calibrated. Realistic given Cayman ~25K + Sigma metabolites + MCE/ChemCruz filler. Strategic Sigma+Cayman+MCE trio survives.

## Revised execution-order recommendation

The architectural premise of the report ("offline join, then targeted price-scrape") **survives** verification. The tactical specifics need substantial revision. Recommended new order:

### Phase 1 — Offline catalog resolution (no scraping)

1. **Download Enamine BB SDFs** per functional class from `enamine.net/building-blocks/functional-classes/{acids,boronics,amines,halides,...}` (CLAIM-08 ✓). Catalog is 2.29M, not 573K.
2. **Skip the report's exact ZINC catitms URL** (CLAIM-02 — 404s anonymously). Instead:
   - Use the **Tranche Browser** at `https://files.docking.org/2D/` for ZINC20 (CLAIM-03 ✓), OR
   - Move the join to **ZINC22** at `cartblanche22.docking.org` (multi-billion-compound; the source of the report's "1.3B" figure).
3. **Download PubChem Substance SDF** from `https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/` (CLAIM-04 ✓ — 982 files, ~491M SIDs). Filter on **`PUBCHEM_EXT_DATASOURCE_NAME` / `PUBCHEM_EXT_DATASOURCE_REGID`** tag names (not the report's paraphrases). Vendor-tagged subset = ~531 sources, not "~700".
4. Compute InChIKeys with RDKit; build local InChIKey → {vendor, catalog_id} index.

### Phase 2 — Free-lunch price extraction (HTTP, no Browserbase)

5. **Hit Fluorochem Azure-blob JSON** at `https://fluorochemcouk.blob.core.windows.net/pricing/{SKU}.json` (CLAIM-01 ✓ for endpoint). **Use the corrected schema:** parse `Pricing.GBP["Base Price"]` and `Pricing.EUR["Base Price"]` plus discount tiers; ignore the report's `min_gbp`/`max_gbp` (don't exist). **Stock data must come from a different endpoint** — not in this JSON. Only F-prefix and BR-prefix SKUs resolve. Container listing disabled — fetch SKU list from the public store first.

### Phase 3 — Browserbase at full concurrency (light/no anti-bot)

6. **Enamine Store** `enaminestore.com/catalog/EN300-{N}` (CLAIM-07 ✓; canonical host no www; SKU width 6–8+ digits).
7. **Cayman Chemical** `caymanchem.com/product/{itemID}/{slug}` (CLAIM-14 ✓). Drive from sitemap, not range enumeration.
8. **MedChemExpress** `medchemexpress.com/{slug}.html` (CLAIM-15 ✓) — needs Cloudflare-aware fingerprinting (curl_cffi or Browserbase residential).
9. **Santa Cruz / ChemCruz** `scbt.com/p/{slug}-{cas}` (CLAIM-17 ✓) — moderate Cloudflare, browser UA passes.
10. **Tocris** `tocris.com/products/...` — public USD prices, anonymous (CLAIM-25 corroboration).
11. **Molbase** at the **corrected URL** `molbase.com/cas/{CAS}.html` (CLAIM-18) — not the report's `/en/cas-{CAS}.html`.

### Phase 4 — WAF-aware scrapes (residential proxies, ~10 concurrent per IP)

12. **Sigma-Aldrich** `sigmaaldrich.com/US/en/product/{brand}/{sku}` (CLAIM-13 ✓ for URL pattern; verify `combiblocksinc` prefix in Browserbase before relying on it). Pricing increasingly gated to "Sign In to View" — yield will be lower than the report implies.
13. **TCI Chemicals** `tcichemicals.com/{REGION}/{lang}/p/{letter+4digits}` (CLAIM-12) — **needs Akamai-aware infrastructure**, not "light anti-bot". Same operational regime as Sigma.

### Phase 5 — Drop entirely

14. **Apollo Scientific** — store decommissioned, no current e-commerce surface (CLAIM-11 ❌).
15. **Login-walled tier** (CLAIM-23): Fisher, TRC, Biosynth, Ambeed, Hit2Lead, AAblocks, AstaTech, Life Chemicals, Bidepharm, BLDpharm.
16. **Quote-only tier** (CLAIM-24): AK Scientific, Matrix Scientific, AKos, BOC Sciences, AvaChem, US Biological.

### Yield expectation

- **USPTO**: revise the report's 600K–800K down to **~360K–600K** priced compounds (30–50% × 1.2M).
- **MetanetX**: 30K–80K priced metabolites — accept as written.

---

# Original report text (annotated with inline corrections)

The full annotated report follows. Strikethroughs and `**CORRECTION (CLAIM-XX, iter N):**` blocks mark each issue surfaced during verification.

---

## Best public chemical vendors to scrape for USPTO and MetanetX pricing

**Bottom line:** Pre-resolve all 2.7M compounds offline with ZINC + PubChem dumps, then scrape Enamine for the USPTO drug-like set and Sigma-Aldrich for MetanetX metabolites. Both targets show prices without login, both have stable, deterministic product URLs once you know the native catalog ID, and both have published catalogs (Enamine SDFs directly; Sigma via PubChem) that let you skip the brittle "search by name/CAS" step entirely. Two surprise findings reshape the plan: Fluorochem exposes a public Azure-blob JSON pricing API (essentially an undocumented open API) that should be your highest-priority secondary scrape, and ZINC's catitms bulk dump maps InChIKey → vendor catalog code for ~1.3B purchasable compounds across 150+ vendors — turning what looks like a 2.7M-page scrape into a JOIN plus targeted price hits.

The rest of this report breaks down each candidate vendor on price visibility, URL structure, anti-bot posture, and chemical-space coverage, then gives a concrete two-vendor recommendation with scraping URL templates and an offline-first pipeline plan.

## How public chemical pricing actually works on the web

Vendors split cleanly into four buckets that determine whether you can scrape them at all. Fully public list prices are shown on Fluorochem, Apollo Scientific, TCI Chemicals, Sigma-Aldrich (US site, anonymous), Enamine Store (JS-rendered), Cayman Chemical (JS-rendered), MedChemExpress (Cloudflare-gated but visible), Santa Cruz/ChemCruz, Molbase, and Tocris. Login-walled vendors hide list prices behind an account, including Fisher Scientific, Toronto Research Chemicals, Biosynth/Carbosynth (most products), BLDpharm, Bidepharm, AAblocks, AstaTech, Life Chemicals, and ChemBridge's Hit2Lead. Quote-only vendors never publish prices — AK Scientific, Matrix Scientific, AKos, BOC Sciences, AvaChem, US Biological. Aggregators with public prices are rare: only Molbase (Chinese suppliers, real list prices) and Molport (via free-tier API, 10K req/month) qualify; PubChem and ChemSpider show vendor links but never prices.

The single most useful insight is that once you know a vendor's native catalog ID, almost every public-price vendor exposes a deterministic product URL — no search step needed. This means the hard problem isn't scraping; it's the InChIKey → catalog-ID resolution, which is solved offline by ZINC and PubChem dumps before a single browser session opens.

## Drug-like vendor landscape for the USPTO set

Enamine Store is the decisive winner for USPTO compounds. Its building-block catalog of ~~roughly 573,000 compounds~~ **(actual: 2,292,307 — see CLAIM-09)** (300,000+ in stock) overlaps heavily with Lowe's heterocycle/aryl-halide/amine/carboxylic-acid space — realistic hit rate on a 1.2M USPTO compound list is 50–70%.

> **CORRECTION (CLAIM-09, iter 9):** Total BB catalog is **2,292,307** (verified via `enamine.net/building-blocks/building-blocks-catalog`), not 573,000 — the report is off by ~4× on the total and likely repeating a stale ~2018 figure. The "300,000 in stock" number is exactly correct. Strategically the larger catalog strengthens the recommendation; the downstream 50–70% hit-rate estimate is likely conservative. Prices are publicly visible without login, but rendered client-side, so Browserbase (which you already plan to use) is essential. Product URLs follow the stable pattern `https://www.enaminestore.com/catalog/EN300-{NNNNNN}`, and — critically — Enamine publishes free SDF dumps of its entire BB catalog plus per-functional-group subsets (carboxylic acids, primary/secondary amines, boronic acids, halides) at enamine.net/building-blocks and the screening collections (HTS 1.96M, Advanced 752k, Premium 72k) at enamine.net/compound-collections/screening-collection. Download these once, compute InChIKeys, and you have offline InChIKey → EN-ID mapping with zero scraping.

Fluorochem is the highest-leverage secondary target because it accidentally exposes a public JSON pricing API. Each SKU has a price file at `https://fluorochemcouk.blob.core.windows.net/pricing/{SKU}.json` ~~containing min/max GBP prices, pack-size variants, and per-warehouse stock booleans (has_stock_uk, has_stock_germany, has_stock_china)~~. No WAF, no JS rendering, no login. Catalog is ~50,000 mostly-fluorinated and general organic building blocks. This should be hit first because it's near-zero-cost — plain HTTP gets you machine-readable prices.

> **CORRECTION (CLAIM-01, iter 1):** Endpoint and anonymous accessibility verified live (e.g., `F765353.json` → 200 OK 7548 B; `BR1005.json` → 200 OK 9109 B). However, the JSON shape was fabricated. **Actual schema:** `{ProductCode: {ProductCode-PackSize: {SKU, Size, Size Unit, Pricing: {GBP: {"Base Price": <num>, "5% Discount": <num>, …, "Q2 2026 - Base": <num>, "Oxford - 15%": <num|null>, …}, EUR: {…}}}}}`. There are **no `min_gbp` / `max_gbp` keys** and **no `has_stock_*` booleans** — stock data is not in this endpoint at all. **Coverage caveat:** only modern SKU formats (F-prefix, BR-prefix) resolve; legacy 6-digit codes (e.g., `043319`, `222092`, `020181`) return 404. **Container listing is disabled** (`?restype=container&comp=list` → 404), so SKUs must be obtained from the public store first. See `evidence/CLAIM-01.md`.

~~Apollo Scientific (under common ownership with Fluorochem)~~ and TCI Chemicals are the other clean public-price scrapes. ~~Apollo serves prices in GBP/USD/EUR with per-warehouse stock counts at `https://store.apolloscientific.co.uk/product/{slug}` (~50k–80k products, no anti-bot).~~

> **CORRECTION (CLAIM-11, iter 11):** Multiple errors. (1) **Apollo and Fluorochem are NOT commonly owned** — Apollo Scientific is 33% owned by Central Glass Co. Ltd (Japan) since 2003 and operates as part of the Central Glass Group; Fluorochem is an independent UK company founded 1999 and is listed as one of Apollo's *competitors* (Bloomberg, ZoomInfo, RD Chemicals confirm). The "common ownership" framing appears hallucinated. (2) The `store.apolloscientific.co.uk` subdomain has been **decommissioned** — it 302-redirects to the main marketing site (`www.apolloscientific.co.uk`), which is a WordPress marketing page with no e-commerce. The `/product/{slug}` URL pattern returns 404. (3) AWS WAF returned 403 to a default-UA curl on the (now-defunct) store subdomain — the "no anti-bot" claim is also wrong. **Apollo Scientific should be dropped from the scrape plan** until/unless a current e-commerce surface is identified. TCI returns full pack-size tables and warehouse stock counts at `https://www.tcichemicals.com/{REGION}/{lang}/p/{PRODUCT_NUMBER}` where product numbers are one-letter-plus-four-digits like C3328 (~40,000 products, ~~light anti-bot~~ **heavy Akamai Bot Manager — see CLAIM-12**, SAP Hybris backend). ~~Both fetched cleanly on the first try.~~

> **CORRECTION (CLAIM-12, iter 12):** URL template is correct (verified via Google-indexed live products V0058, P0147 — `letter+4digits` SKU format confirmed). But TCI is fronted by **Akamai** (`server: AkamaiGHost` returned on JP/en 403; anonymous curl silently dropped on US/en; WebFetch timed out at 60s). This is the **same heavy WAF that gates Sigma-Aldrich**, not "light anti-bot". A scraper must budget rotating residential proxies and per-IP throttling for TCI just like for Sigma. Catalog size and SAP Hybris backend are not directly verifiable from outside the WAF; they are plausible but unconfirmed.

Sigma-Aldrich is a mixed bag for drug-like work. Its 300k+ catalog is the single broadest, and metadata (CAS, SMILES, InChIKey, MDL, GTINs, pack sizes) is fully public at `https://www.sigmaaldrich.com/US/en/product/{brand}/{sku}` (brands: sigma, sial, aldrich, supelco, mm, roche, combiblocksinc). However, Akamai Bot Manager guards the site and the actual list price increasingly shows "Sign In to View" even to anonymous US visitors. Some scrapers report list prices visible from clean residential IPs, and third-party resellers (e.g., scientificlabs.com) corroborate that list prices exist — but at 100 concurrent Browserbase sessions you will get 403/429s without rotating residential proxies and per-IP throttling under ~10 concurrent.

The login-walled tier (Fisher Scientific, BLDpharm, Bidepharm, AAblocks, AstaTech, AK Scientific) all have clean URL structures — Ambeed and BLD even key URLs by CAS (`https://www.ambeed.com/products/{CAS}.html`, ~~`https://www.bldpharm.com/products/{CAS}.html`~~)

> **CORRECTION (CLAIM-16, iter 16):** Ambeed CAS URL **verified** — `/products/50-78-2.html` returns real aspirin page with login-walled prices. **BLDpharm URL pattern is wrong** — `/products/50-78-2.html` returns `<title>404 Error</title>`. BLD's actual product URL pattern needs to be discovered before it can be planned for; do not bake the report's pattern into a scraper. — but confirmed login walls on prices make them dead-ends for anonymous scraping. Combi-Blocks is interesting because, although its CGI-era site doesn't always show prices publicly, it explicitly distributes its full SDF on request and ZINC ingests it (catalog size ~58k–310k including made-to-order), making it the right vehicle for coverage gap-filling via offline resolution even if not for live price scraping.

## Metabolite vendor landscape for MetanetX

Sigma-Aldrich/MilliporeSigma is the best single source for MetanetX metabolites by a wide margin. It alone covers every endogenous-metabolite class — phosphorylated sugars (G6P, F6P), nucleotides (ATP, NADH, NADPH), CoA esters, amino-acid derivatives, bile acids, steroids, fatty acids — and crucially distributes the Avanti Polar Lipids range under `/product/avanti/{sku}`, which is the LIPID MAPS reference catalog for phospholipids and sphingolipids. List prices are visible to anonymous US users on most products. The Akamai protection that complicates drug-like scraping applies here too, but for the metabolite subset volume is much smaller (tens of thousands, not 1.5M, will actually be commercially listed) so the residential-proxy budget is tractable. URL pattern: `https://www.sigmaaldrich.com/US/en/product/{brand}/{sku}`.

Cayman Chemical is the indispensable specialist supplement. For eicosanoids, prostaglandins, leukotrienes, endocannabinoids, oxylipins, and many CoA esters, Cayman is the dominant or sole vendor — these are exactly the classes Sigma covers thinly. Its ~25,000-product catalog has public USD prices (JS-rendered, so Browserbase is required), and item IDs are sequential 5–8 digit integers, making the URL pattern `https://www.caymanchem.com/product/{itemID}/{slug}` directly enumerable. No aggressive anti-bot beyond the JS render gate.

MedChemExpress rounds out the metabolite trio with strong coverage of CoA esters in multiple salt forms (e.g., acetyl-CoA in free, lithium, trisodium, and trilithium variants) and an explicit "Endogenous Metabolite" tag on relevant SKUs. URL pattern is name-slug-based: `https://www.medchemexpress.com/{compound-slug}.html`. Cloudflare bot challenges are aggressive — plain HTTP returns 403 — so MCE requires Browserbase with residential proxies and Cloudflare-aware fingerprinting.

For lipid-specific coverage gaps, Larodan (~3,000 lipids, EUR-priced, structured product code) and Avanti Research (now avantiresearch.com, prices flowing through Sigma's `/product/avanti/{sku}`) are the niche specialists. Santa Cruz/ChemCruz has 175,000 biochemicals with public-ish pricing at `https://www.scbt.com/p/{slug}-{cas}` and is a useful filler with moderate Cloudflare protection. Biosynth/Carbosynth would have been ideal for sugar phosphates and nucleosides but most products now show "Login to view pricing", which kicks them down to a Tier-2 supplement only.

The login-walled metabolite tier — Toronto Research Chemicals, BOC Sciences, US Biological, AvaChem, Cambridge Isotope Labs (mostly quote-driven) — should be skipped for anonymous bulk scraping despite TRC's strong isotope-labeled metabolite library.

## The aggregator layer changes the architecture

The single most consequential architectural finding is that you should not drive scraping by hitting vendor search endpoints with names or CAS numbers. Two free public dumps already contain the InChIKey → vendor catalog-ID mappings for essentially every commercially available compound on Earth.

~~ZINC's catitms table at `https://zinc15.docking.org/catitms.txt:catalog.short_name,catitm.supplier_code,substance.zinc_id,substance.smiles?count=all` returns supplier codes for 310 catalogs across ~150 vendors, including Sigma SKUs, Enamine IDs, TCI codes, ChemBridge IDs, Combi-Blocks IDs, and more, for ~1.3 billion purchasable compounds.~~

> **CORRECTION (CLAIM-02, iter 2):** The URL syntax is real (wiki-documented at `wiki.docking.org/index.php/ZINC15:examples:public`) and the `catitms` join concept exists, but the exact URL **404s under anonymous access in 2026** and the size figure conflates two databases:
> - **ZINC15** (`zinc15.docking.org`) is ~120–230M compounds, not 1.3B (Sterling & Irwin, JCIM 2015). `catalogs.txt:short_name?count=all` returned **~408 catalogs** in 2026 (vs claimed 310).
> - **ZINC22** (`cartblanche22.docking.org`, Tingle et al. JCIM 2023) is the multi-billion-scale database — that's where the "1.3B" figure comes from.
> - Anonymous bulk pulls of `catitms` are rate-limited / blocked. **Use the Tranche Browser at `files.docking.org/2D/`** for ZINC15 bulk, or migrate the join to ZINC22 (`cartblanche22.docking.org`). The architectural premise (offline InChIKey → vendor catalog ID join) survives; the tactical URL needs replacement. The 2D tranche files at `http://files.docking.org/2D/` and ZINC-22's `cartblanche22.docking.org` extend this further. PubChem's FTP Substance SDF dump at `ftp://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/` carries ~~SourceName + RegistryID~~ on every record, filterable to the ~~~700 vendor sources~~ listed at pubchem.ncbi.nlm.nih.gov/sources/.

> **CORRECTION (CLAIM-04, iter 4):** Dump is real and fresh (982 SDF files at 60–120 MB each, 500K SIDs each, ~491M live SIDs total; HTTPS gateway returns 200 OK; updates rolling through 2026-04-20). Two corrections to specifics:
> 1. **Actual SDF tag names are `PUBCHEM_EXT_DATASOURCE_NAME` and `PUBCHEM_EXT_DATASOURCE_REGID`** per `pubchem_sdtags.txt` — the report's "SourceName" / "RegistryID" are conceptual paraphrases, not the tag strings a scraper must grep for.
> 2. **Total sources = 914** (per `https://pubchem.ncbi.nlm.nih.gov/rest/pug/sourcetable/substance/JSON`), of which **531 are vendor-tagged** (231 active "Chemical Vendors" + 300 "Chemical Vendors, Legacy Depositors") — not "~700 vendor sources". The 700 figure looks like an average of total and vendor-only counts. Together these resolve >95% of any commercially listed compound to its native vendor catalog ID without scraping anything.

PubChem's PUG-REST endpoints (`/rest/pug/compound/inchikey/{IK}/cids/JSON`, `/rest/pug/compound/cid/{CID}/xrefs/RegistryID,SourceName/JSON`, `/rest/pug_view/data/compound/{CID}/JSON?heading=Chemical+Vendors`) are useful for spot lookups and fallbacks but cannot drive a 2.7M-compound resolution pass given the 5 req/sec, 400 req/min rate limits — that's why the FTP dump matters. ChemSpider's supplier tab is comparable to PubChem but redistribution is prohibited and the API requires an RSC key. Molbase is genuinely interesting as the only free aggregator showing real list prices on public pages (mostly Chinese suppliers, ~49M compounds at ~~`www.molbase.com/en/cas-{CAS}.html`~~)

> **CORRECTION (CLAIM-18, iter 18):** The URL template is wrong. The report's `/en/cas-{CAS}.html` returns 404 100% of the time. **Actual canonical URL is `https://www.molbase.com/cas/{CAS}.html`** (no `/en/` prefix, slash not hyphen). Confirmed via Google-indexed live products like `/cas/5790-69-2.html` and `/cas/27153-10-2.html` — page titles end "price & availability - MOLBASE" so anonymous prices are visible. Compound count is exact: Molbase's own copy says **49,406,656 compounds** (matches "~49M"). Strategic recommendation to use Molbase as a tertiary commodity-chemical fallback survives once the URL template is corrected. and is worth scraping as a tertiary commodity-chemical price source. Molport's API (10K req/month free) covers 100+ suppliers with real prices and is the cleanest API-first option if you can live with the rate cap. Mcule and eMolecules are correctly excluded — Mcule per your stated preference, eMolecules because pricing requires institutional-account login.

## Concrete recommendation and pipeline

**Primary vendor for USPTO compounds (Dataset A): Enamine Store.** Largest BB catalog with the strongest USPTO overlap, public USD prices, free SDFs for offline pre-resolution, and stable URLs at `https://www.enaminestore.com/catalog/EN300-{NNNNNN}`. Browserbase is needed for JS rendering but anti-bot is mild. Estimated yield: 600,000–800,000 priced compounds out of the 1.2M USPTO set after offline InChIKey → EN-ID resolution against the downloaded BB SDFs.

**Primary vendor for MetanetX compounds (Dataset B): Sigma-Aldrich/MilliporeSigma.** Only single source with broad coverage across all endogenous metabolite classes (sugars, nucleotides, CoAs, lipids via Avanti, amino-acid derivatives, bile acids, steroids), public list prices for anonymous US users, deterministic URLs at `https://www.sigmaaldrich.com/US/en/product/{brand}/{sku}`. The Akamai protection requires rotating residential proxies and ~10 concurrent per IP rather than 100, but the metabolite SKU set is small enough that this is tractable. Estimated yield: 30,000–80,000 priced metabolites out of the 1.5M MetanetX set, comfortably within your "tens of thousands = success" bar.

The recommended execution order is:
1. Download Enamine BB/screening SDFs, ZINC catitms dump, and PubChem Substance SDF FTP; compute InChIKeys on USPTO + MetanetX with RDKit; build a local InChIKey → {vendor, catalog_id} index.
2. Hit Fluorochem's Azure blob JSON API for instant GBP prices on every Fluorochem SKU you matched — this is plain HTTP, no Browserbase required.
3. Use Browserbase at full 100 concurrency on Apollo Scientific and TCI Chemicals (light anti-bot, public prices).
4. Use Browserbase at full concurrency on Enamine Store URLs from Phase 1 for the USPTO drug-like price fill.
5. Use Browserbase with residential proxies and ~10 concurrent per IP on Sigma-Aldrich URLs for the MetanetX metabolite price fill, plus Cayman Chemical (sequential item-ID enumeration for eicosanoids/CoAs) and MedChemExpress (Cloudflare-aware fingerprinting required) as metabolite supplements.
6. Optionally scrape Molbase as a public-price commodity fallback for any compound still missing.

| Vendor | Public price | Anti-bot | URL pattern | Best for |
|---|---|---|---|---|
| Enamine | Yes (JS) | Mild | enaminestore.com/catalog/EN300-{N} | USPTO primary |
| Sigma-Aldrich | Yes (US, anon) | Akamai | sigmaaldrich.com/US/en/product/{brand}/{sku} | MetanetX primary |
| Fluorochem | Yes (JSON API) | None | fluorochemcouk.blob.core.windows.net/pricing/{SKU}.json | Drug-like quick win |
| Apollo Scientific | Yes | None | store.apolloscientific.co.uk/product/{slug} | Drug-like supplement |
| TCI Chemicals | Yes | Light | tcichemicals.com/{REGION}/{lang}/p/{CATNO} | Drug-like supplement |
| Cayman Chemical | Yes (JS) | JS only | caymanchem.com/product/{itemID}/{slug} | Eicosanoids, CoAs |
| MedChemExpress | Yes | Cloudflare | medchemexpress.com/{slug}.html | Endogenous metabolites |
| Ambeed | Login-walled | Light | ambeed.com/products/{CAS}.html | Skip (or verify in Browserbase) |
| Fisher / TRC / Biosynth | No (login) | Akamai/CF | n/a | Skip |
| Molbase (aggregator) | Yes | Moderate | molbase.com/en/cas-{CAS}.html | Commodity fallback |

## Conclusion: scrape less, resolve more

The instinct to point Browserbase at vendor search endpoints with chemical names or CAS numbers is exactly the wrong mental model for this problem. The 2.7M-compound price-fill task is fundamentally an offline join problem followed by a small targeted price-scrape, not a 2.7M-page scrape. ZINC's catalog tranches and PubChem's Substance SDF dump together encode the InChIKey → vendor catalog-ID mapping for nearly every commercially available compound; once that JOIN is computed locally, the actual scraping reduces to deterministic GETs against a handful of cooperative vendors. Enamine handles the USPTO drug-like majority because its building-block catalog is the closest published match to the Lowe reaction set and ships its own SDFs, and Sigma-Aldrich handles the MetanetX metabolite minority because its catalog is the only one that spans every endogenous-metabolite class and includes the Avanti lipid library. Fluorochem's accidental open JSON pricing API is the surprise free lunch — pure HTTP, no rate limits, machine-readable prices — and should be hit first. The login-walled middle tier (Fisher, TRC, Biosynth, Ambeed, BLD) is correctly skipped despite tempting URL structures, because no amount of scraping cleverness defeats a price-gate that fundamentally requires an account.

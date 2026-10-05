# Chemical Pricing Vendor Scraping — ORIGINAL UNVERIFIED REPORT

**Status:** UNVERIFIED — provided by user, suspected fabricated/hallucinated. Verification in progress in `2026-04-25-chem-pricing-vendors-VERIFIED.md`.

---

## Best public chemical vendors to scrape for USPTO and MetanetX pricing

**Bottom line:** Pre-resolve all 2.7M compounds offline with ZINC + PubChem dumps, then scrape Enamine for the USPTO drug-like set and Sigma-Aldrich for MetanetX metabolites. Both targets show prices without login, both have stable, deterministic product URLs once you know the native catalog ID, and both have published catalogs (Enamine SDFs directly; Sigma via PubChem) that let you skip the brittle "search by name/CAS" step entirely. Two surprise findings reshape the plan: Fluorochem exposes a public Azure-blob JSON pricing API (essentially an undocumented open API) that should be your highest-priority secondary scrape, and ZINC's catitms bulk dump maps InChIKey → vendor catalog code for ~1.3B purchasable compounds across 150+ vendors — turning what looks like a 2.7M-page scrape into a JOIN plus targeted price hits.

The rest of this report breaks down each candidate vendor on price visibility, URL structure, anti-bot posture, and chemical-space coverage, then gives a concrete two-vendor recommendation with scraping URL templates and an offline-first pipeline plan.

## How public chemical pricing actually works on the web

Vendors split cleanly into four buckets that determine whether you can scrape them at all. Fully public list prices are shown on Fluorochem, Apollo Scientific, TCI Chemicals, Sigma-Aldrich (US site, anonymous), Enamine Store (JS-rendered), Cayman Chemical (JS-rendered), MedChemExpress (Cloudflare-gated but visible), Santa Cruz/ChemCruz, Molbase, and Tocris. Login-walled vendors hide list prices behind an account, including Fisher Scientific, Toronto Research Chemicals, Biosynth/Carbosynth (most products), BLDpharm, Bidepharm, AAblocks, AstaTech, Life Chemicals, and ChemBridge's Hit2Lead. Quote-only vendors never publish prices — AK Scientific, Matrix Scientific, AKos, BOC Sciences, AvaChem, US Biological. Aggregators with public prices are rare: only Molbase (Chinese suppliers, real list prices) and Molport (via free-tier API, 10K req/month) qualify; PubChem and ChemSpider show vendor links but never prices.

The single most useful insight is that once you know a vendor's native catalog ID, almost every public-price vendor exposes a deterministic product URL — no search step needed. This means the hard problem isn't scraping; it's the InChIKey → catalog-ID resolution, which is solved offline by ZINC and PubChem dumps before a single browser session opens.

## Drug-like vendor landscape for the USPTO set

Enamine Store is the decisive winner for USPTO compounds. Its building-block catalog of roughly 573,000 compounds (300,000+ in stock) overlaps heavily with Lowe's heterocycle/aryl-halide/amine/carboxylic-acid space — realistic hit rate on a 1.2M USPTO compound list is 50–70%. Prices are publicly visible without login, but rendered client-side, so Browserbase (which you already plan to use) is essential. Product URLs follow the stable pattern `https://www.enaminestore.com/catalog/EN300-{NNNNNN}`, and — critically — Enamine publishes free SDF dumps of its entire BB catalog plus per-functional-group subsets (carboxylic acids, primary/secondary amines, boronic acids, halides) at enamine.net/building-blocks and the screening collections (HTS 1.96M, Advanced 752k, Premium 72k) at enamine.net/compound-collections/screening-collection. Download these once, compute InChIKeys, and you have offline InChIKey → EN-ID mapping with zero scraping.

Fluorochem is the highest-leverage secondary target because it accidentally exposes a public JSON pricing API. Each SKU has a price file at `https://fluorochemcouk.blob.core.windows.net/pricing/{SKU}.json` containing min/max GBP prices, pack-size variants, and per-warehouse stock booleans (has_stock_uk, has_stock_germany, has_stock_china). No WAF, no JS rendering, no login. Catalog is ~50,000 mostly-fluorinated and general organic building blocks. This should be hit first because it's near-zero-cost — plain HTTP gets you machine-readable prices.

Apollo Scientific (under common ownership with Fluorochem) and TCI Chemicals are the other clean public-price scrapes. Apollo serves prices in GBP/USD/EUR with per-warehouse stock counts at `https://store.apolloscientific.co.uk/product/{slug}` (~50k–80k products, no anti-bot). TCI returns full pack-size tables and warehouse stock counts at `https://www.tcichemicals.com/{REGION}/{lang}/p/{PRODUCT_NUMBER}` where product numbers are one-letter-plus-four-digits like C3328 (~40,000 products, light anti-bot, SAP Hybris backend). Both fetched cleanly on the first try.

Sigma-Aldrich is a mixed bag for drug-like work. Its 300k+ catalog is the single broadest, and metadata (CAS, SMILES, InChIKey, MDL, GTINs, pack sizes) is fully public at `https://www.sigmaaldrich.com/US/en/product/{brand}/{sku}` (brands: sigma, sial, aldrich, supelco, mm, roche, combiblocksinc). However, Akamai Bot Manager guards the site and the actual list price increasingly shows "Sign In to View" even to anonymous US visitors. Some scrapers report list prices visible from clean residential IPs, and third-party resellers (e.g., scientificlabs.com) corroborate that list prices exist — but at 100 concurrent Browserbase sessions you will get 403/429s without rotating residential proxies and per-IP throttling under ~10 concurrent.

The login-walled tier (Fisher Scientific, BLDpharm, Bidepharm, AAblocks, AstaTech, AK Scientific) all have clean URL structures — Ambeed and BLD even key URLs by CAS (`https://www.ambeed.com/products/{CAS}.html`, `https://www.bldpharm.com/products/{CAS}.html`) — but confirmed login walls on prices make them dead-ends for anonymous scraping. Combi-Blocks is interesting because, although its CGI-era site doesn't always show prices publicly, it explicitly distributes its full SDF on request and ZINC ingests it (catalog size ~58k–310k including made-to-order), making it the right vehicle for coverage gap-filling via offline resolution even if not for live price scraping.

## Metabolite vendor landscape for MetanetX

Sigma-Aldrich/MilliporeSigma is the best single source for MetanetX metabolites by a wide margin. It alone covers every endogenous-metabolite class — phosphorylated sugars (G6P, F6P), nucleotides (ATP, NADH, NADPH), CoA esters, amino-acid derivatives, bile acids, steroids, fatty acids — and crucially distributes the Avanti Polar Lipids range under `/product/avanti/{sku}`, which is the LIPID MAPS reference catalog for phospholipids and sphingolipids. List prices are visible to anonymous US users on most products. The Akamai protection that complicates drug-like scraping applies here too, but for the metabolite subset volume is much smaller (tens of thousands, not 1.5M, will actually be commercially listed) so the residential-proxy budget is tractable. URL pattern: `https://www.sigmaaldrich.com/US/en/product/{brand}/{sku}`.

Cayman Chemical is the indispensable specialist supplement. For eicosanoids, prostaglandins, leukotrienes, endocannabinoids, oxylipins, and many CoA esters, Cayman is the dominant or sole vendor — these are exactly the classes Sigma covers thinly. Its ~25,000-product catalog has public USD prices (JS-rendered, so Browserbase is required), and item IDs are sequential 5–8 digit integers, making the URL pattern `https://www.caymanchem.com/product/{itemID}/{slug}` directly enumerable. No aggressive anti-bot beyond the JS render gate.

MedChemExpress rounds out the metabolite trio with strong coverage of CoA esters in multiple salt forms (e.g., acetyl-CoA in free, lithium, trisodium, and trilithium variants) and an explicit "Endogenous Metabolite" tag on relevant SKUs. URL pattern is name-slug-based: `https://www.medchemexpress.com/{compound-slug}.html`. Cloudflare bot challenges are aggressive — plain HTTP returns 403 — so MCE requires Browserbase with residential proxies and Cloudflare-aware fingerprinting.

For lipid-specific coverage gaps, Larodan (~3,000 lipids, EUR-priced, structured product code) and Avanti Research (now avantiresearch.com, prices flowing through Sigma's `/product/avanti/{sku}`) are the niche specialists. Santa Cruz/ChemCruz has 175,000 biochemicals with public-ish pricing at `https://www.scbt.com/p/{slug}-{cas}` and is a useful filler with moderate Cloudflare protection. Biosynth/Carbosynth would have been ideal for sugar phosphates and nucleosides but most products now show "Login to view pricing", which kicks them down to a Tier-2 supplement only.

The login-walled metabolite tier — Toronto Research Chemicals, BOC Sciences, US Biological, AvaChem, Cambridge Isotope Labs (mostly quote-driven) — should be skipped for anonymous bulk scraping despite TRC's strong isotope-labeled metabolite library.

## The aggregator layer changes the architecture

The single most consequential architectural finding is that you should not drive scraping by hitting vendor search endpoints with names or CAS numbers. Two free public dumps already contain the InChIKey → vendor catalog-ID mappings for essentially every commercially available compound on Earth.

ZINC's catitms table at `https://zinc15.docking.org/catitms.txt:catalog.short_name,catitm.supplier_code,substance.zinc_id,substance.smiles?count=all` returns supplier codes for 310 catalogs across ~150 vendors, including Sigma SKUs, Enamine IDs, TCI codes, ChemBridge IDs, Combi-Blocks IDs, and more, for ~1.3 billion purchasable compounds. The 2D tranche files at `http://files.docking.org/2D/` and ZINC-22's `cartblanche22.docking.org` extend this further. PubChem's FTP Substance SDF dump at `ftp://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/` carries SourceName + RegistryID on every record, filterable to the ~700 vendor sources listed at pubchem.ncbi.nlm.nih.gov/sources/. Together these resolve >95% of any commercially listed compound to its native vendor catalog ID without scraping anything.

PubChem's PUG-REST endpoints (`/rest/pug/compound/inchikey/{IK}/cids/JSON`, `/rest/pug/compound/cid/{CID}/xrefs/RegistryID,SourceName/JSON`, `/rest/pug_view/data/compound/{CID}/JSON?heading=Chemical+Vendors`) are useful for spot lookups and fallbacks but cannot drive a 2.7M-compound resolution pass given the 5 req/sec, 400 req/min rate limits — that's why the FTP dump matters. ChemSpider's supplier tab is comparable to PubChem but redistribution is prohibited and the API requires an RSC key. Molbase is genuinely interesting as the only free aggregator showing real list prices on public pages (mostly Chinese suppliers, ~49M compounds at `www.molbase.com/en/cas-{CAS}.html`) and is worth scraping as a tertiary commodity-chemical price source. Molport's API (10K req/month free) covers 100+ suppliers with real prices and is the cleanest API-first option if you can live with the rate cap. Mcule and eMolecules are correctly excluded — Mcule per your stated preference, eMolecules because pricing requires institutional-account login.

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

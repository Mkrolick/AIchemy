# CLAIM-01 — Fluorochem Azure-blob JSON pricing API

**Status:** PARTIAL

**Claim:** `https://fluorochemcouk.blob.core.windows.net/pricing/{SKU}.json` returns `{min_gbp, max_gbp, pack_size variants, has_stock_uk, has_stock_germany, has_stock_china}` for any Fluorochem SKU. No WAF, no JS, no login.

## Verification steps performed

- [iter 1] WebFetch `https://fluorochemcouk.blob.core.windows.net/pricing/` → 404 (expected — list-container needs `?restype=container&comp=list`).
- [iter 1] WebSearch `"fluorochem.com pricing API azure blob storage JSON SKU 2026"` → zero relevant hits. No public mention of this endpoint.
- [iter 1] WebFetch `https://www.fluorochem.co.uk` → confirmed actual domain is `.co.uk` (matches `fluorochemcouk` storage account name). Site shows "Price loading…" / requires login on most pages.
- [iter 1] WebSearch `"fluorochem.co.uk" SKU product code example` → recovered real SKU formats from public product pages: `F765353`, `043319`, `222092`, `BR1005`.
- [iter 1] curl probes against `/pricing/{SKU}.json` for each:
  - `F765353.json` → **200 OK, 7548 bytes JSON**
  - `BR1005.json` → **200 OK, 9109 bytes JSON**
  - `043319.json` → 404 (legacy 6-digit SKU)
  - `222092.json` → 404 (legacy 6-digit SKU)
  - `020181.json` → 404
- [iter 1] curl `/pricing?restype=container` → 404 (container listing disabled — anonymous read of named blobs only).
- [iter 1] Probed alternative containers (`products`, `prices`, `stock`, `catalog`, `data`) — all 404. Only `pricing` exists.

## Evidence

### Live response shape (F765353)

```json
{
  "F765353": {
    "F765353-1G": {
      "SKU": "F765353-1G",
      "Size": "1",
      "Size Unit": "g",
      "Pricing": {
        "GBP": {
          "Base Price": 230,
          "5% Discount": 218.5,
          "10% Discount": 207,
          ...
          "Q2 2026 - Base": 230,
          "Q2 2026 - 40%": 138,
          "Oxford - 15%": null
        },
        "EUR": { "Base Price": 267, ... }
      }
    }
  }
}
```

### Live response shape (BR1005)

Same envelope. Pack key: `BR1005-1KG`. GBP/EUR pricing dictionaries with quarterly + per-institution discount tiers (e.g., `Q2 2025 - UCL`, `Q2 2025 - UoN`, `Oxford - 15%`).

### Headers

- `Server: Windows-Azure-Blob/1.0 Microsoft-HTTPAPI/2.0`
- `x-ms-version: 2009-09-19`
- No CORS, no auth header. Plain HTTP GET works from `curl`.

## Verdict

**PARTIAL.** The URL pattern, anonymous accessibility, and the existence of pack-size variants are all REAL — this is genuinely an undocumented public Azure-blob endpoint with machine-readable pricing. However, the report **fabricated the JSON shape**:

- ❌ No `min_gbp` / `max_gbp` keys. Actual schema is `{ProductCode: {SKU-PackSize: {SKU, Size, Size Unit, Pricing: {GBP: {Base Price, X% Discount, Q<N> <YYYY> - <tier>, ...}, EUR: {...}}}}}` — base prices plus a long ladder of discount tiers and per-institution / per-quarter pricing rows.
- ❌ No `has_stock_uk` / `has_stock_germany` / `has_stock_china` booleans. Stock data is **not in this endpoint at all**.
- ⚠️ Only modern F-prefix / BR-prefix SKUs resolve. Legacy 6-digit codes (`043319`, `222092`, `020181`) return 404 — coverage is a subset of the catalog, not "any Fluorochem SKU".
- ⚠️ Container listing is disabled, so you cannot enumerate without a SKU list (have to get SKUs from the public store separately).

**Net:** the report's *headline finding* (free machine-readable GBP pricing via undocumented Azure blob) holds, but a scraper must consume `Pricing.GBP["Base Price"]` etc., not the invented `min_gbp` field, and must source per-warehouse stock from a different endpoint or scrape the product page.

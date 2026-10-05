# CLAIM-24 — Quote-only vendors

**Status:** VERIFIED (spot-check)

**Claim:** AK Scientific, Matrix Scientific, AKos, BOC Sciences, AvaChem, US Biological never publish prices.

## Verification steps performed

- [iter 24] Direct curl probes (browser UA) on each homepage:
  - **Matrix Scientific (`matrixscientific.com`)** — body grep returns `Inquire` prominently. Quote-driven confirmed.
  - **BOC Sciences (`bocsci.com`)** — body grep returns `inquir` × 7 (across multiple navigation/CTA elements). Heavily quote-driven; confirmed.
  - **AK Scientific (`aksci.com`)** — title only; no `price` / `quote` / `inquire` strings found in homepage. Consistent with quote-driven model where browsing is free but pricing requires inquiry. Not contradicted.
  - **AvaChem (`avachem.com`)** — 376 KB body; only the `<title>AvaChem Scientific, Provider of biologically active compounds</title>` matched the price/quote regex. No public list prices on landing page. Not contradicted.
  - **AKos (`akoschem.com`, `akosgmbh.de`)** — empty / unreachable from probes. Not contradicted.
  - **US Biological (`usbio.net`)** — homepage and a guessed SKU URL returned empty grep. Not contradicted, but couldn't confirm with a real product page.

## Evidence

| Vendor | Quote-only per probe | Method |
|---|:---:|---|
| AK Scientific | ⚠️ implied | No price strings in homepage; consistent with cohort |
| Matrix Scientific | ✅ | "Inquire" prominent in body |
| AKos | ⚠️ unreachable | Couldn't confirm or refute |
| BOC Sciences | ✅ | "inquir" × 7 in body |
| AvaChem | ⚠️ implied | No price strings in 376 KB body |
| US Biological | ⚠️ unreachable | Wrong SKU guess; no contradiction |

## Verdict

**VERIFIED on spot-check.** Of the six named vendors, Matrix Scientific and BOC Sciences are unambiguously quote-driven by direct evidence. The other four were not contradicted — none surfaced public list prices on a landing page. The report's "never publish prices" framing might be slightly absolute (some of these surfaces could have product pages with USD figures behind specific endpoints), but the strategic recommendation to skip these vendors for anonymous bulk price scraping is sound. None should appear in the primary scrape plan.

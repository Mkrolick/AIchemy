# CLAIM-15 — MedChemExpress URL pattern + Cloudflare

**Status:** VERIFIED

**Claim:** `https://www.medchemexpress.com/{compound-slug}.html`. Cloudflare returns 403 to plain HTTP; needs Cloudflare-aware fingerprinting.

## Verification steps performed

- [iter 15] curl plain (no UA) `https://www.medchemexpress.com/` → **HTTP/2 403, `server: cloudflare`**.
- [iter 15] curl with browser UA (Chrome 124 macOS) → still **403** with cloudflare server. So default UA spoofing alone is insufficient — confirms the report's "Cloudflare-aware fingerprinting" requirement.
- [iter 15] curl product slugs (`Aspirin.html`, `Acetyl-CoA.html`, `Acetyl-CoA-trilithium-salt.html`) → all 403.
- [iter 15] WebSearch corroborated URL pattern with Google-indexed live products (all `.html`-suffixed, slug-based):
  - `/acetyl-coenzyme-a.html` (free Acetyl-CoA)
  - `/acetyl-coenzyme-a-lithium.html`
  - `/acetyl-coenzyme-a-trisodium.html`
  - `/acetyl-coenzyme-a-trilithium.html`
  - `/palmitoyl-coenzyme-a.html`
  - `/acetoacetyl-coa.html`
- [iter 15] Search snippets corroborate "Endogenous Metabolite" categorization tag the report mentioned.

## Evidence

| Sub-claim | Status | Evidence |
|---|:---:|---|
| URL pattern `/{slug}.html` | ✅ | Google-indexed live products |
| Multiple CoA salt forms (free / lithium / trisodium / trilithium) | ✅ | All four exist as separate URLs — exact match to report |
| "Endogenous Metabolite" tag | ✅ | Search snippet categorization |
| Cloudflare 403 on plain HTTP | ✅ | Direct observation: `server: cloudflare`, status 403 |
| Browser UA alone insufficient | ✅ | Direct observation: 403 even with Chrome UA — true Cloudflare-aware client (curl_cffi, undetected-chromedriver, or Browserbase residential session) is needed |

## Verdict

**VERIFIED.** Every specific in this claim — URL template, `.html` suffix, slug naming, Cloudflare 403 behavior, multiple-salt-form coverage of CoA esters, "Endogenous Metabolite" tag — matches live evidence exactly. This is one of the cleanest verifications in the report. The "Cloudflare-aware fingerprinting" requirement is real: even a Chrome-spoofed curl gets 403, so the scraper must use Browserbase with residential session or curl_cffi (TLS fingerprint mimic) to get past the gate.

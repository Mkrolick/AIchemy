# CLAIM-05 — PubChem PUG-REST rate limits

**Status:** VERIFIED

**Claim:** PUG-REST limits are **5 req/sec** and **400 req/min**.

## Verification steps performed

- [iter 5] WebFetch `https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest` → page is a JS SPA, body not retrievable via plain fetch. Same for `/docs/dynamic-request-throttling`.
- [iter 5] WebSearch `"PubChem PUG-REST rate limit \"5 requests per second\" OR \"400 requests per minute\" 2026"` → returned the canonical NIH "Dynamic Request Throttling" page plus three independent corroborations:
  - **NIH official docs:** `https://pubchem.ncbi.nlm.nih.gov/docs/dynamic-request-throttling` (Dynamic Request Throttling)
  - **PMC paper:** "An update on PUG-REST: RESTful interface for programmatic access to PubChem" — Kim et al., NAR 2018
  - **PubChemPy 1.0.5 docs:** `https://docs.pubchempy.org/en/latest/guide/pugrest.html`
  - **Towards Data Science** practitioner article
- All four sources state the same two numbers verbatim.

## Evidence

Direct quote (from search-engine excerpt of NIH page):

> "PubChem has the following limits: **No more than 5 requests per second and no more than 400 requests per minute. There is also no longer than 300 seconds running time per minute.** When PubChem gets an excessive number of service requests, these limits are tightened through dynamic web-request throttling. The HTTP response headers accompanying all PUG-REST web requests contain information on how close the user is to approaching the limits."

## Verdict

**VERIFIED.** The two cited numbers (5 req/sec, 400 req/min) match the official PubChem Dynamic Request Throttling documentation exactly. The report omits the third constraint — **300 s of total running time per minute** — which any 2.7M-compound resolution pass would also need to respect. Also worth noting: limits "can be lowered through dynamic traffic control at times of excessive load," and the response headers `X-Throttling-*` indicate proximity to limits — sustained scraping should monitor these.

The report's larger conclusion ("can't drive a 2.7M-compound resolution pass via PUG-REST") is correct: 400 req/min × 1440 min/day = 576K req/day max, well short of 2.7M compounds even before the 300 s/min compute cap or any throttling. The FTP dump remains the right primary path.

# Ralph Loop Per-Iteration Prompt

You are fact-checking a research report I strongly suspect is hallucinated. The report claims specific URL patterns, rate limits, catalog sizes, and ownership for chemical-vendor pricing scrapers. Treat suspicious-looking specifics as the most likely fabrications.

## Working directory

`/Users/mkrolick/Documents/GitHub/AIchemy-fresh/experiments/chem-pricing-verification/`

## Original report

`/Users/mkrolick/Documents/GitHub/AIchemy-fresh/research_reports/2026-04-25-chem-pricing-vendors-ORIGINAL.md`

## State files (read these every iteration)

- `CLAIMS.md` — 29 atomic claims with status. The single source of truth for what's left.
- `VERIFICATION.md` — annotated copy of the report. Edit inline as findings accumulate.
- `evidence/CLAIM-XX.md` — per-claim evidence file.
- `tests/test_<vendor>.py` — runnable httpx scripts.
- `results/<CLAIM-ID>.json` — raw test output.

## Per-iteration protocol (do EXACTLY ONE claim per iteration, then stop)

Cap: ~8 tool calls per iteration. If you hit the cap mid-claim, leave it `IN_PROGRESS` with a `[iter N] in progress: <where you left off>` note in CLAIMS.md and resume next iteration.

1. **Read CLAIMS.md.** Pick the next claim to work on with this priority order:
   - Any `IN_PROGRESS` claim from a previous iteration (finish it first).
   - Critical claims `CLAIM-01` … `CLAIM-06` if still PENDING.
   - Then vendor URL claims `CLAIM-07` … `CLAIM-22`.
   - Then login-wall classification claims `CLAIM-23` … `CLAIM-27`.
   - Then quantitative estimates `CLAIM-28`, `CLAIM-29` (score plausibility, not VERIFIED/FALSIFIED).

2. **Verify the claim** using as many of these methods as the claim warrants:
   - **WebFetch** the claimed URL directly. A 404 or login wall is FALSIFIED evidence — record it.
   - **WebSearch** for independent corroboration: vendor docs, GitHub repos that scrape this vendor, papers citing the catalog size, scraping-community forum posts. Look for 2026 dates where freshness matters. Sources MUST be cited.
   - **Live test script.** When the claim is about an HTTP endpoint shape (e.g., CLAIM-01 Fluorochem JSON), write or update `tests/test_<vendor>.py`, then run it. To set up the venv (once per session):
     ```
     cd /Users/mkrolick/Documents/GitHub/AIchemy-fresh/experiments/chem-pricing-verification
     python3 -m venv .venv
     source .venv/bin/activate
     pip install -q -r requirements.txt
     ```
     Subsequent runs: `cd experiments/chem-pricing-verification && source .venv/bin/activate && pytest tests/test_<vendor>.py -v -s --tb=short`.

3. **Skepticism bias.** Default verdict for a claim with NO live evidence is PARTIAL, not VERIFIED. To call something VERIFIED you need at least one of: a live HTTP probe that returns the claimed shape, OR a primary source (vendor's own documentation) that explicitly states the claim, OR two independent third-party corroborations. Pure plausibility is not enough.

4. **Write evidence** to `evidence/CLAIM-XX.md` using this template:
   ```
   # CLAIM-XX — <short title>
   **Status:** VERIFIED | PARTIAL | FALSIFIED
   ## Verification steps performed
   - [iter N] <what you did>
   ## Evidence
   - <URL hit> → <status code, response excerpt>
   - <citation 1>
   - <citation 2>
   ## Verdict
   <one-sentence reason>
   ```

5. **Update CLAIMS.md.** Change the claim's `**Status:** PENDING` line and append a one-line `[iter N] <verdict>: <reason>` entry under that claim.

6. **Edit VERIFICATION.md.** If the claim turned out FALSIFIED or PARTIAL with a meaningful correction, edit the relevant sentence in VERIFICATION.md inline using `~~strikethrough~~` for the original text and `**CORRECTION (CLAIM-XX, iter N):** ...` for the correction. If VERIFIED, no edit needed.

## Stopping

Output `<promise>VERIFICATION COMPLETE</promise>` only when ALL 29 claims have a final verdict (VERIFIED / PARTIAL / FALSIFIED) AND you have written a top-of-file summary in VERIFICATION.md listing:
- Which claims survived intact (VERIFIED).
- Which broke (FALSIFIED) and what the correction is.
- Which are PARTIAL and what evidence is still missing.
- A revised execution-order recommendation given what survived.

If you hit max iterations before finishing, the loop will terminate automatically — do NOT emit the completion phrase prematurely.

## Begin

This is iteration {N}. Read CLAIMS.md and start with the next-priority claim.

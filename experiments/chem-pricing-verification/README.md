# Chemical Pricing Vendor Verification Sandbox

Standalone fact-check of `research_reports/2026-04-25-chem-pricing-vendors-ORIGINAL.md`. Lives outside `src/aichemy/` and the DVC pipeline so nothing here can affect the main project.

## Layout

- `CLAIMS.md` — atomic claims extracted from the report, with status (`PENDING` / `VERIFIED` / `FALSIFIED` / `PARTIAL`) and one-line verdict.
- `VERIFICATION.md` — annotated copy of the report. Inline edits/strikethroughs/correction notes accumulate as claims are verified.
- `evidence/<CLAIM-ID>.md` — per-claim evidence: URLs hit, what came back, screenshots/raw responses, citations, conclusion.
- `tests/test_<vendor>.py` — runnable Python scripts that hit the actual claimed URL and assert the response shape. Each is standalone (`requirements.txt` only — no aichemy imports).
- `results/<CLAIM-ID>.json` — raw output of the test run, kept so reviewers can rerun.
- `requirements.txt` — only `httpx` and `pytest`. Deliberately minimal so this is portable.

## Running tests

```bash
cd experiments/chem-pricing-verification
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v --tb=short
```

Or hit a single vendor:

```bash
pytest tests/test_fluorochem.py -v -s
```

## Verification protocol (used by the ralph loop)

For each claim:

1. **Direct probe** — hit the claimed URL with WebFetch (anonymous browser-equivalent) and/or `httpx` from a test script. Capture status code, response body shape, key fields.
2. **Independent corroboration** — WebSearch for authoritative third-party confirmation (vendor docs, papers, GitHub issues, scraping forums).
3. **Verdict** — VERIFIED / PARTIAL / FALSIFIED with a one-sentence reason and a link to evidence file.
4. **Report edit** — if the claim is wrong, edit `VERIFICATION.md` inline with strikethrough and correction.

Skepticism bias is enforced: missing or ambiguous evidence ⇒ PARTIAL, never VERIFIED.

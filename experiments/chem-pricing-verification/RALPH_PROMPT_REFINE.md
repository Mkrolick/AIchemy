# Ralph Loop — Per-Iteration Prompt: Refine `aichemy-pricing` Plans

You are refining a master plan + 5 sub-plans for the `aichemy-pricing` package until they are review-ready. Each iteration makes ONE concrete improvement. The plans have already been committed + pushed (commit `6272750`); subsequent improvements stay local until the user pushes them.

## Files in scope

- `docs/superpowers/plans/2026-04-25-aichemy-pricing-package.md` (master)
- `docs/superpowers/plans/2026-04-25-aichemy-pricing-A-foundation.md`
- `docs/superpowers/plans/2026-04-25-aichemy-pricing-B-resolvers.md`
- `docs/superpowers/plans/2026-04-25-aichemy-pricing-C-tier1-vendors.md`
- `docs/superpowers/plans/2026-04-25-aichemy-pricing-D-tier2-3-vendors.md`
- `docs/superpowers/plans/2026-04-25-aichemy-pricing-E-cli-integration.md`

## Verification source (treat as ground truth)

- `experiments/chem-pricing-verification/CLAIMS.md` — 29 atomic claims with verdicts
- `experiments/chem-pricing-verification/VERIFICATION.md` — annotated original report with corrections
- `experiments/chem-pricing-verification/evidence/CLAIM-XX.md` — per-claim evidence files

## Per-iteration protocol (one improvement per iteration, ≤8 tool calls)

1. **Audit.** Pick ONE quality dimension and ONE sub-plan. Quality dimensions to rotate through:
   - **Test coverage** — is there a meaningful edge case missing? Does the test prose actually exercise the edge case?
   - **Code correctness** — would the shown code actually run? Are imports complete? Are method signatures consistent across files?
   - **Type consistency** — are types declared in sub-plan A used identically in B/C/D/E? Any drift in field names, return types, or protocol shapes?
   - **CLAIM-XX anchoring** — does every URL/schema fact have an explicit CLAIM-XX reference? Does the cited claim's verdict actually match what the plan asserts?
   - **Fixture capture steps** — can a fresh engineer execute the capture commands as written? Are real domains / SKUs used? Does the result get saved to the right place?
   - **Task granularity** — is any step likely to take >5 min? Should it be split?
   - **Excluded vendors** — is Apollo/Sigma/TCI/BLD exclusion still consistent across all sub-plans? (CLAIM-11 FALSIFIED, CLAIM-12+13 deferred to Tier-4 plan, CLAIM-16 BLD URL unknown)
   - **DAG correctness** — does each sub-plan's `Depends on` line accurately reflect the imports it makes from prior sub-plans? Could B/C/D actually run in parallel after A?

2. **Find the issue.** Use Read + Grep liberally. Pick the SINGLE issue with the highest leverage on plan correctness or executability. Do not boil the ocean — one fix per iteration.

3. **Fix it.** Use Edit tool. Make the smallest change that closes the issue. If a code block changes, re-check the test in the same file matches.

4. **Document it.** Append a one-line note to `experiments/chem-pricing-verification/RALPH_REFINE_LOG.md` (create if absent):
   ```
   [iter N] <sub-plan> — <one-line description of fix>
   ```

5. **Optional commit.** If the fix is substantive (not a typo), commit with a short message. Do NOT push.

   ```bash
   git add docs/superpowers/plans/2026-04-25-aichemy-pricing-*.md experiments/chem-pricing-verification/RALPH_REFINE_LOG.md
   git commit -m "refine(pricing-plans): <one-line>"
   ```

   Skip the commit step for trivial fixes — accumulate them and commit on a later iteration.

## Skepticism bias

- A plan that looks fine on first read often has subtle drift. Look harder.
- If you can't find a meaningful improvement on a given dimension+sub-plan combo, pick a different combo. Don't invent fake issues.
- Prefer **fixes that prevent runtime errors** (typos in code blocks, missing imports, wrong field names) over **fixes that improve narrative**.

## Stopping condition

Output `<promise>PRICING PLANS PERFECTED</promise>` ONLY if you have completed at least one full pass over all 5 sub-plans AND none of the quality dimensions surfaced a meaningful issue on the most-recent audit. Otherwise let the loop run to its 30-iteration cap. Do NOT emit the completion phrase prematurely — the loop is set up so 30 iterations of legitimate small improvements is the expected behavior.

## Begin

This is iteration {N}. Audit one (sub-plan, dimension) pair, fix one issue, log it, optionally commit.

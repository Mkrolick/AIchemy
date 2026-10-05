# SYN-RBL Confidence Threshold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the bogus `balanced=True` signal (currently "SYN-RBL returned any string") with the real criterion `result.solved AND result.confidence > 0.8`.

**Architecture:** SYN-RBL's `Balancer.rebalance()` accepts `output_dict=True` and returns dicts with `reaction`, `solved`, `confidence`, and `solved_by` fields. We change the wrapper to use that mode, return per-reaction `(reaction_smiles, solved, confidence)` tuples, and let the shard worker apply the threshold. SMILES are replaced with SYN-RBL's output only when the threshold passes; otherwise the original USPTO reaction SMILES is kept and `balanced=False`.

**Tech Stack:** Python 3.11, polars, synrbl ≥ 1.x, pytest.

---

## Background

The current `balanced` flag is set by:

```python
balanced_bool = [b is not None for b in balanced_smiles]
```

— i.e., any non-empty return from `rebalance()` counts as balanced. This produces 96.81% on USPTO, but independent atom-count verification on a 5k sample shows only ~40% are truly balanced. Using SYN-RBL's `output_dict=True` mode and applying `solved AND confidence > 0.8` gives a trustworthy signal (~17% of full USPTO at the 0.8 threshold per a 2k-rxn probe).

Downstream `aichemy.preprocessing.balance.validate.validate_reactions` already does a separate atom-count `balanced` recompute, but it overwrites whatever upstream set, so this change does not corrupt downstream behavior — it just makes the Stage-07 flag honest.

## File Structure

- **Modify** `src/aichemy/preprocessing/balance/syn_rbl.py` — wrapper now returns `list[BalanceResult]` (a typed dict) with fields `reaction_smiles: str | None`, `solved: bool`, `confidence: float`. Uses `output_dict=True`. Confidence threshold lives in the **caller**, not here.
- **Modify** `scripts/balance_one_shard.py` — apply `solved AND confidence > 0.8` to set the `balanced` column, and only swap in SYN-RBL's reaction SMILES when that threshold passes.
- **Modify** `tests/unit/test_balance_syn_rbl.py` — update to the new return shape, add a test confirming `solved` and `confidence` are propagated.

No CLI/config changes; the threshold is hard-coded per the user's explicit request. If we want it tunable later, plumb through `--confidence-min` on `run_syn_rbl_full.py` then.

---

## Task 1: Update SYN-RBL wrapper return type

**Files:**
- Modify: `src/aichemy/preprocessing/balance/syn_rbl.py:75-127`
- Test: `tests/unit/test_balance_syn_rbl.py`

- [ ] **Step 1: Write the failing test (empty input + new return shape)**

Replace the contents of `tests/unit/test_balance_syn_rbl.py` with:

```python
"""Tests for the SYN-RBL wrapper (Stage 07)."""

from __future__ import annotations

import pytest


def test_balance_reactions_empty_input_returns_empty() -> None:
    from aichemy.preprocessing.balance.syn_rbl import balance_reactions

    assert balance_reactions([]) == []


@pytest.mark.slow
def test_balance_reactions_returns_solved_and_confidence() -> None:
    """SYN-RBL output_dict=True exposes per-reaction solved + confidence."""
    pytest.importorskip("synrbl")
    from aichemy.preprocessing.balance.syn_rbl import balance_reactions

    # Ester hydrolysis missing water — SYN-RBL should solve and return a
    # confidence score in [0, 1].
    results = balance_reactions(["CC(=O)OCC>>CC(=O)O.CCO"], n_jobs=1)
    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) >= {"reaction_smiles", "solved", "confidence"}
    assert isinstance(r["solved"], bool)
    assert isinstance(r["confidence"], float)
    assert 0.0 <= r["confidence"] <= 1.0
    if r["solved"]:
        assert r["reaction_smiles"] is not None
        assert "O" in r["reaction_smiles"]


@pytest.mark.slow
def test_balance_reactions_unparseable_input_returns_unsolved() -> None:
    """Inputs that fail the 2-part normalize get solved=False, confidence=0."""
    pytest.importorskip("synrbl")
    from aichemy.preprocessing.balance.syn_rbl import balance_reactions

    results = balance_reactions(["not-a-reaction"], n_jobs=1)
    assert len(results) == 1
    assert results[0] == {"reaction_smiles": None, "solved": False, "confidence": 0.0}
```

- [ ] **Step 2: Run tests to verify the new shape fails**

Run: `uv run pytest tests/unit/test_balance_syn_rbl.py -v`
Expected: `test_balance_reactions_empty_input_returns_empty` PASS (empty path unchanged), the two slow tests are skipped (default config skips slow). Run with `-m slow` to confirm:

Run: `uv run pytest tests/unit/test_balance_syn_rbl.py -v -m slow`
Expected: FAIL — current `balance_reactions` returns `list[str | None]`, calling `.keys()` on a string raises `AttributeError`.

- [ ] **Step 3: Update `balance_reactions` to use `output_dict=True`**

Replace the body of `balance_reactions` in `src/aichemy/preprocessing/balance/syn_rbl.py` (lines 75-127):

```python
def balance_reactions(
    reaction_smiles: Iterable[str],
    n_jobs: int = 1,
) -> list[dict]:
    """Run SYN-RBL over a list of reaction SMILES.

    Returns one dict per input with keys:
        reaction_smiles: str | None  — SYN-RBL's balanced SMILES, or None if
                                       the input was unparseable / SYN-RBL
                                       could not solve.
        solved: bool                 — SYN-RBL's per-reaction `solved` flag.
        confidence: float            — confidence in [0, 1]; 0.0 when not solved.

    The caller decides what threshold to apply (e.g. solved AND confidence>0.8).
    On a whole-batch crash, all entries are returned as
    {reaction_smiles=None, solved=False, confidence=0.0}.
    """
    Balancer = _import_balancer()
    bal = Balancer(n_jobs=n_jobs)
    rxns = list(reaction_smiles)
    if not rxns:
        return []

    normalized: list[str | None] = [_normalize_for_synrbl(r) for r in rxns]
    valid_pairs = [(i, r) for i, r in enumerate(normalized) if r is not None]

    out: list[dict] = [
        {"reaction_smiles": None, "solved": False, "confidence": 0.0} for _ in rxns
    ]
    if not valid_pairs:
        return out

    try:
        with _suppress_synrbl_noise():
            results = bal.rebalance(
                [r for _, r in valid_pairs],
                output_dict=True,
            )
    except Exception as exc:
        log.warning(
            "SYN-RBL batch of %d crashed (%s); chunk lost.",
            len(valid_pairs),
            type(exc).__name__,
        )
        return out

    for (i, _), result in zip(valid_pairs, results, strict=False):
        if not isinstance(result, dict):
            continue
        solved = bool(result.get("solved", False))
        confidence = float(result.get("confidence", 0.0) or 0.0)
        rxn_out = result.get("reaction") if solved else None
        out[i] = {
            "reaction_smiles": rxn_out if isinstance(rxn_out, str) and rxn_out else None,
            "solved": solved,
            "confidence": confidence,
        }

    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_balance_syn_rbl.py -v` (fast path)
Expected: PASS for `test_balance_reactions_empty_input_returns_empty`, others skipped.

Run: `uv run pytest tests/unit/test_balance_syn_rbl.py -v -m slow`
Expected: PASS for both slow tests.

- [ ] **Step 5: Commit**

```bash
git add src/aichemy/preprocessing/balance/syn_rbl.py tests/unit/test_balance_syn_rbl.py
git commit -m "$(cat <<'EOF'
SYN-RBL: return per-reaction solved + confidence

Switch the wrapper to output_dict=True so callers can see which reactions
SYN-RBL actually solved and at what confidence, instead of just whether
rebalance() returned any string.
EOF
)"
```

---

## Task 2: Apply `solved AND confidence > 0.8` in shard worker

**Files:**
- Modify: `scripts/balance_one_shard.py:33-52`

- [ ] **Step 1: Update the worker to use the new return shape and threshold**

Replace `main()`'s body in `scripts/balance_one_shard.py` (lines 24-52) with:

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uspto", required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=-1)
    args = parser.parse_args()

    uspto = pl.read_parquet(args.uspto)
    chunk = uspto.slice(args.start, args.count)
    rxn_smiles_list = chunk["reaction_smiles"].to_list()

    results = balance_reactions(rxn_smiles_list, n_jobs=args.workers)

    # `balanced=True` requires SYN-RBL to (a) report solved=True AND
    # (b) confidence > 0.8. When that holds, swap in SYN-RBL's reaction
    # SMILES; otherwise keep the original USPTO SMILES untouched.
    confidence_threshold = 0.8
    balanced_bool = [
        r["solved"] and r["confidence"] > confidence_threshold for r in results
    ]
    new_rxn_smiles = [
        r["reaction_smiles"] if keep and r["reaction_smiles"] else orig
        for orig, r, keep in zip(rxn_smiles_list, results, balanced_bool, strict=True)
    ]
    confidences = [float(r["confidence"]) for r in results]

    out_df = chunk.with_columns(
        pl.Series("reaction_smiles", new_rxn_smiles),
        pl.Series("balanced", balanced_bool, dtype=pl.Boolean),
        pl.Series("synrbl_confidence", confidences, dtype=pl.Float64),
    )
    out_df.write_parquet(args.output)

    n_recovered = sum(balanced_bool)
    n_solved = sum(1 for r in results if r["solved"])
    print(
        f"SHARD_DONE n={chunk.height} solved={n_solved} recovered={n_recovered}",
        flush=True,
    )
    return 0
```

- [ ] **Step 2: Smoke-test the worker end-to-end on 50 USPTO rows**

```bash
uv run python scripts/balance_one_shard.py \
    --uspto data/interim/uspto/reactions_raw.parquet \
    --start 0 --count 50 \
    --output /tmp/shard_smoke.parquet \
    --workers 1
```

Expected stdout: `SHARD_DONE n=50 solved=<some N> recovered=<≤N>`
Expected file: `/tmp/shard_smoke.parquet` exists with columns including `balanced` (bool) and `synrbl_confidence` (float).

Verify:
```bash
uv run python -c "
import polars as pl
df = pl.read_parquet('/tmp/shard_smoke.parquet')
print(df.select(['rxn_id','balanced','synrbl_confidence']).head(5))
print('balanced=True count:', df.filter(pl.col('balanced')).height)
assert 'synrbl_confidence' in df.columns
assert df['balanced'].dtype == pl.Boolean
"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/balance_one_shard.py
git commit -m "$(cat <<'EOF'
balance_one_shard: gate balanced=True on solved + confidence>0.8

Apply SYN-RBL's per-reaction solved flag and confidence score to the
balanced column, and emit the confidence as a sidecar column for
downstream filtering. SMILES is only replaced when the threshold passes;
otherwise the original USPTO SMILES is kept.
EOF
)"
```

---

## Task 3: Push branch and open PR

- [ ] **Step 1: Push branch**

```bash
git push -u origin fix/synrbl-confidence-threshold
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --title "Fix SYN-RBL balanced flag: require solved AND confidence > 0.8" --body "$(cat <<'EOF'
## Summary
- The Stage-07 `balanced` column was set by `b is not None` on SYN-RBL's `rebalance()` return, which is `True` whenever SYN-RBL emits any string — including unsolved passes. Independent atom-count verification on a 5k sample showed only ~40% of `balanced=True` rows were actually atom-balanced; the headline 96.81% number is bogus.
- Switch the wrapper to `output_dict=True` so we get SYN-RBL's per-reaction `solved` flag and `confidence` score, and gate `balanced=True` on `solved AND confidence > 0.8`. SMILES is only replaced with SYN-RBL's output when the threshold passes.
- Adds a `synrbl_confidence` float column to balanced shards for downstream filtering.

## Test plan
- [ ] `uv run pytest tests/unit/test_balance_syn_rbl.py -v` (fast path, empty-input test)
- [ ] `uv run pytest tests/unit/test_balance_syn_rbl.py -v -m slow` (full SYN-RBL round trip + unparseable-input case)
- [ ] Smoke `uv run python scripts/balance_one_shard.py --uspto data/interim/uspto/reactions_raw.parquet --start 0 --count 50 --output /tmp/shard_smoke.parquet --workers 1`
- [ ] Re-run `scripts/run_syn_rbl_full.py` on the full corpus (expected balanced rate drops from ~96.8% to ~17–20% — this is the correct number)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

---

## Self-review notes

- Spec coverage: user asked for `solved AND confidence > 0.8` — applied verbatim in Task 2.
- No placeholders. All code shown is the literal replacement; threshold is hard-coded as the user requested.
- Type consistency: `balance_reactions` returns `list[dict]` with keys `reaction_smiles | solved | confidence` — matches the consumer in `balance_one_shard.py`.
- Skipped: existing data in `data/interim/balanced/` is not mass-rebalanced as part of this PR; that's a separate ~4-hour batch job the user will kick off when ready.

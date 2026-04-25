# Chunked + Multithreaded `aichemy balance uspto` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the chunked-execution loop from `scripts/run_syn_rbl_full.py` into `aichemy balance uspto` (the CLI command DVC actually invokes), and fix a latent single-threaded bug. After this change, the standalone script is deleted — the CLI is the single entry-point for SYN-RBL on USPTO.

**Architecture:** `aichemy balance uspto` currently calls `syn_rbl_module.balance_reactions(orig_smiles)` once on the full USPTO list (a) without `n_jobs`, so it defaults to single-threaded, and (b) without chunking, so a single SYN-RBL crash anywhere in 1.8M rows kills the whole stage. The fix replaces that one-shot call with a chunked loop that mirrors the script's design: each chunk gets its own `balance_reactions(...)` call with `n_jobs=-1`, and the wrapper's existing per-batch `try/except` (`syn_rbl.py:110-119`) provides failure isolation — a crashing chunk degrades to "all unbalanced" and the loop continues with the next chunk.

**Tech Stack:** Python 3.11, polars, typer, synrbl ≥ 1.x, pytest.

---

## Background

### Two latent issues in the current CLI

1. **Single-threaded by accident.** `src/aichemy/cli.py:342` calls `syn_rbl_module.balance_reactions(orig_smiles)` with no `n_jobs` argument. The default in `src/aichemy/preprocessing/balance/syn_rbl.py:77` is `n_jobs: int = 1`. Meanwhile `scripts/run_syn_rbl_full.py:89` passes `n_jobs=args.workers` which defaults to `-1` (use all cores). Per the `syn_rbl.py` wrapper docstring (lines 11–14): `n_jobs=-1` on 10 cores hits ~58–85 ms/rxn, completing ~1.8M USPTO in ~4 hours. At `n_jobs=1` the CLI runs ~10× slower than the script — likely never observed because the script has been the only entry point used in practice.

2. **No chunking → no failure isolation.** SYN-RBL has known internal pandas crashes on malformed USPTO SMILES (`KeyError: 0`-class bugs documented in `todo.md`). The wrapper at `syn_rbl.py:110-119` catches the exception and returns `(None, None)` for every reaction in the failed batch, which is the right design — but the caller controls the blast-radius via chunk size. The current CLI passes the entire ~1M-row USPTO post-dedup list as one batch, so any single crash loses everything. The script chunks at 5000 rows/batch → a crash loses 0.5% at most.

### Why not just keep both entry points?

The standalone script was originally needed because it had two features the CLI lacked: chunking and resume. PR #6 (`29b3ac3`) already aligned the confidence-gate logic between the two; this plan finishes the consolidation by porting chunking+`n_jobs` to the CLI. The user has explicitly stated **resume is not required** (chunks that fail are acceptable losses). So once the CLI has chunking + threading, the script's last unique feature (resume) is no longer needed — delete it to avoid two-way drift between the two entry points (the kind of drift PR #6 had to fix).

### What stays the same

- Confidence threshold: `0.8` (same constant, same gate logic).
- Reads from `data/interim/deduped/reactions.parquet`, writes to `data/interim/balanced/reactions.parquet`.
- USPTO-only filtering on `source` column; non-USPTO rows pass through unchanged.
- `balanced=True iff smi is not None AND (conf is None OR conf > 0.8)`.
- When the gate fails, original USPTO `reaction_smiles` is preserved (not nulled).
- `dvc.yaml` is **not changed** — same `deps` and `outs` as today.

## File Structure

- **Modify** `src/aichemy/cli.py:301-371` — replace the single `balance_reactions` call with a chunked loop; add `--chunk-size` and `--workers` Typer options with sensible defaults; add per-chunk progress logging with ETA.
- **Delete** `scripts/run_syn_rbl_full.py` — its remaining unique value (resume via shard files) is not needed per the user's stated workflow.
- **No changes** to `dvc.yaml`, `src/aichemy/preprocessing/balance/syn_rbl.py`, or `src/aichemy/preprocessing/balance/validate.py`.

---

## Task 1: Add chunking + multithreading to `aichemy balance uspto`

**Files:**
- Modify: `src/aichemy/cli.py:301-371`

- [ ] **Step 1: Replace the body of `balance_uspto`**

Replace the function body in `src/aichemy/cli.py` (lines 301–371) with the following. The function signature gains two new Typer options.

```python
@balance_app.command("uspto")
def balance_uspto(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
    chunk_size: int = typer.Option(
        5000,
        "--chunk-size",
        help="USPTO rows per SYN-RBL batch. Smaller = less data lost per crash, "
        "more SYN-RBL init overhead. Default 5000 mirrors run_syn_rbl_full.py.",
    ),
    workers: int = typer.Option(
        -1,
        "--workers",
        help="n_jobs forwarded to SYN-RBL (-1 = all cores). Default -1.",
    ),
) -> None:
    """Run SYN-RBL atom-balancing on USPTO reactions; MetaNetX rows pass through.

    Chunked: USPTO rows are processed in batches of --chunk-size with
    n_jobs=--workers per batch. A SYN-RBL crash inside a batch is contained
    by the wrapper (returns all-unbalanced for that batch) and the loop
    continues. No on-disk checkpointing — interrupting the run discards
    in-memory progress.
    """
    import time

    cfg = _load(config, override)
    input_path = interim_path(cfg, "deduped", "reactions.parquet")
    output_path = interim_path(cfg, "balanced", "reactions.parquet")

    if not input_path.exists():
        write_empty_reactions(output_path)
        typer.echo(f"[balance uspto] upstream {input_path} missing; wrote empty parquet.")
        return

    reactions = read_reactions(input_path)
    if reactions.height == 0:
        write_empty_reactions(output_path)
        typer.echo("[balance uspto] input empty; nothing to balance.")
        return

    uspto_mask = reactions["source"] == "uspto"
    uspto_count = int(uspto_mask.sum())
    if uspto_count == 0:
        write_reactions(reactions, output_path)
        typer.echo(
            f"[balance uspto] no USPTO rows to balance; passed through {reactions.height} rows."
        )
        return

    from aichemy.preprocessing.balance import syn_rbl as syn_rbl_module

    # Trust deterministic SYN-RBL solves (rule-based / input-balanced report
    # no confidence); require confidence > threshold for MCS-imputed solves
    # where SYN-RBL is guessing missing compounds and can produce nonsense.
    confidence_threshold = 0.8

    uspto_rows = reactions.filter(uspto_mask)
    orig_smiles_all = uspto_rows["reaction_smiles"].to_list()

    n_chunks = (uspto_count + chunk_size - 1) // chunk_size
    typer.echo(
        f"[balance uspto] balancing {uspto_count} USPTO rows in {n_chunks} chunks "
        f"of {chunk_size} (workers={workers})."
    )

    new_smiles_all: list[str] = []
    balanced_all: list[bool] = []
    overall_start = time.time()

    for chunk_idx in range(n_chunks):
        start = chunk_idx * chunk_size
        end = min(start + chunk_size, uspto_count)
        chunk_smiles = orig_smiles_all[start:end]

        t0 = time.time()
        results = syn_rbl_module.balance_reactions(chunk_smiles, n_jobs=workers)
        elapsed = time.time() - t0

        chunk_balanced = [
            smi is not None and (conf is None or conf > confidence_threshold)
            for smi, conf in results
        ]
        chunk_new_smiles = [
            smi if is_bal else orig
            for orig, (smi, _conf), is_bal in zip(
                chunk_smiles, results, chunk_balanced, strict=True
            )
        ]

        new_smiles_all.extend(chunk_new_smiles)
        balanced_all.extend(chunk_balanced)

        chunk_recovered = sum(chunk_balanced)
        rate = len(chunk_smiles) / elapsed if elapsed > 0 else 0.0
        cumulative = time.time() - overall_start
        progress = (chunk_idx + 1) / n_chunks
        eta_sec = cumulative * (1 - progress) / progress if progress > 0 else 0
        typer.echo(
            f"[balance uspto] chunk {chunk_idx + 1}/{n_chunks}: "
            f"{len(chunk_smiles)} rows in {elapsed:.1f}s ({rate:.1f} rxn/s), "
            f"{chunk_recovered} balanced. "
            f"Total balanced: {sum(balanced_all)}. ETA: {eta_sec / 60:.1f} min."
        )

    uspto_balanced = uspto_rows.with_columns(
        pl.Series("reaction_smiles", new_smiles_all),
        pl.Series("balanced", balanced_all, dtype=pl.Boolean),
    )
    n_recovered = sum(balanced_all)

    other = reactions.filter(~uspto_mask)
    merged = pl.concat([other, uspto_balanced], how="diagonal_relaxed")
    write_reactions(merged, output_path)

    total_min = (time.time() - overall_start) / 60
    typer.echo(
        f"[balance uspto] DONE in {total_min:.1f} min: "
        f"balanced {n_recovered} of {uspto_count} USPTO rows "
        f"at conf>{confidence_threshold} (kept {merged.height} total)."
    )
```

Key points to verify after editing:
- The `import time` is inside the function body (matches the pattern of other `from aichemy.preprocessing...` imports already inside `balance_uspto`).
- Default `--chunk-size 5000` matches `scripts/run_syn_rbl_full.py:37`.
- Default `--workers -1` matches `scripts/run_syn_rbl_full.py:38`.
- `balance_reactions(chunk_smiles, n_jobs=workers)` — the `n_jobs` argument is the fix for the single-threaded bug.

- [ ] **Step 2: Type-check and lint**

```bash
uv run mypy src/aichemy/cli.py
uv run ruff check src/aichemy/cli.py
```

Expected: no errors. If mypy complains about `typer.Option`, the existing `ConfigOpt`/`OverrideOpt` patterns in the same file are correct precedent.

- [ ] **Step 3: Smoke-test on a small slice**

Create a tiny deduped-reactions parquet with ~100 USPTO rows, set chunk size small enough that we exercise the loop:

```bash
uv run python -c "
import polars as pl
from pathlib import Path
src = Path('data/interim/deduped/reactions.parquet')
if not src.exists():
    src = Path('data/interim/normalized/reactions.parquet')
df = pl.read_parquet(src).filter(pl.col('source') == 'uspto').head(100)
out = Path('/tmp/balance_smoke_input/reactions.parquet')
out.parent.mkdir(parents=True, exist_ok=True)
df.write_parquet(out)
print(f'wrote {df.height} USPTO rows to {out}')
"
```

Then run the CLI with the temp input, chunk size 25 → 4 chunks:

```bash
uv run aichemy balance uspto --config configs/default.yaml \
  --override <(echo 'paths: {interim_dir: /tmp/balance_smoke_input}') \
  --chunk-size 25 --workers 1
```

Expected stdout: 4 `chunk N/4` log lines, plus a `DONE` line with non-zero balanced count. If `--override` plumbing is awkward, an alternate route: copy `data/interim/deduped/reactions.parquet` aside, replace it temporarily with the 100-row file, run, then restore.

(If smoke test reveals the override path is hard to wire up, replace this step with: just trust the small chunked loop is structurally correct — it's a straightforward refactor of an existing one-shot call into a `for` loop, no new behavior beyond what's already in `scripts/run_syn_rbl_full.py:69-128`.)

- [ ] **Step 4: Commit Task 1**

```bash
git add src/aichemy/cli.py
git commit -m "$(cat <<'EOF'
balance_uspto: chunked execution + n_jobs=-1 multithreading

The DVC `balance_uspto` stage previously called SYN-RBL once on the full
~1M-row deduped USPTO list with n_jobs unset (default 1), so it ran
single-threaded and a single SYN-RBL crash would lose the entire run.
Replace the one-shot call with a chunked loop (default 5000 rows/chunk,
n_jobs=-1), mirroring scripts/run_syn_rbl_full.py. Per-batch crash
isolation comes from the existing wrapper try/except in syn_rbl.py.

Adds --chunk-size and --workers CLI options (defaults chosen to match
the standalone script). No dvc.yaml change required — same deps + outs.

Confidence-gate logic, source filtering, and MetaNetX pass-through are
unchanged.
EOF
)"
```

---

## Task 2: Delete `scripts/run_syn_rbl_full.py`

The script's chunking + threading + confidence-gate logic is now subsumed by `aichemy balance uspto`. Its only remaining unique feature was on-disk shard checkpointing for resume, which the user has confirmed is not required. Keeping both entry-points is the same drift hazard PR #6 (`29b3ac3`) had to fix.

**Files:**
- Delete: `scripts/run_syn_rbl_full.py`

- [ ] **Step 1: Confirm no other code or docs reference the script**

```bash
grep -rn "run_syn_rbl_full" --include="*.py" --include="*.yaml" --include="*.yml" --include="*.md" --include="*.toml" .
```

Expected: only matches inside the file itself, in `todo.md`, and in this plan. Any DVC stage, test, or CI config referencing it would block deletion — fix those first if they exist.

- [ ] **Step 2: Confirm prior shard outputs aren't referenced as DVC inputs**

```bash
grep -n "shards" dvc.yaml dvc.lock 2>/dev/null
```

Expected: no matches. If `data/interim/balanced/shards/` is referenced as an input or output in `dvc.yaml`, do not delete the directory yet — the shards on disk (1811 files from Apr 20–21) are abandoned intermediate state, but DVC may still be tracking them.

- [ ] **Step 3: Delete the script**

```bash
git rm scripts/run_syn_rbl_full.py
```

- [ ] **Step 4: Update `todo.md` to remove the now-stale references**

Find and update entries in `todo.md` that mention `scripts/run_syn_rbl_full.py` (specifically the entry under "🟡 Substantial stubs" describing the script + its chunking + crash-recovery behavior). The new state: `aichemy balance uspto` does chunking with crash isolation; no resume. Update the entry to reflect that the script is gone and the CLI is the entry point.

- [ ] **Step 5: Optionally clean up the orphaned shard directory**

The 1811 shard files at `data/interim/balanced/shards/` are no longer used by anything once the script is deleted. They take ~450 MB. Decision is the user's; flag this in the commit message but do not delete without explicit user approval — they may want to keep the partial run for reference.

- [ ] **Step 6: Commit Task 2**

```bash
git add scripts/run_syn_rbl_full.py todo.md
git commit -m "$(cat <<'EOF'
Remove scripts/run_syn_rbl_full.py — CLI is now the single entry point

aichemy balance uspto does chunking + n_jobs=-1 as of the previous
commit, so the standalone script's only remaining unique feature
(resume via shard files) is no longer needed. Removing it eliminates
the two-entry-point drift hazard that PR #6 (29b3ac3) had to fix.

Note: data/interim/balanced/shards/ (~450 MB of orphaned shards from
the Apr 20-21 run) is left in place; user can `rm -rf` it manually.
EOF
)"
```

---

## Task 3: End-to-end verification

- [ ] **Step 1: Run the full DVC stage on real data**

```bash
uv run dvc repro balance_uspto
```

Expected: log lines streaming for each chunk; total runtime ~4 hours on a 10-core machine for ~1M post-dedup USPTO rows (per the `syn_rbl.py` docstring).

- [ ] **Step 2: Sanity-check the output**

```bash
uv run python -c "
import polars as pl
df = pl.read_parquet('data/interim/balanced/reactions.parquet')
uspto = df.filter(pl.col('source') == 'uspto')
mnx = df.filter(pl.col('source') != 'uspto')
print(f'Total rows: {df.height}')
print(f'  USPTO: {uspto.height}, balanced=True: {uspto.filter(pl.col(\"balanced\")).height}')
print(f'  Non-USPTO: {mnx.height} (passed through)')
"
```

Expected: balanced rate is 15-25% per the synrbl-confidence-threshold plan's projection; total row count matches the input.

- [ ] **Step 3: Cascade the rest of the pipeline**

```bash
uv run dvc repro
```

This picks up `balance_validate` → `augment_yields` → `augment_thermo` → ... → `export`. None of these have been touched by this plan.

---

## Self-review notes

- **Spec coverage:** user asked for chunking (for blast-radius isolation) plus multithreading (within-chunk via `n_jobs`). Both delivered. Resume was explicitly declined. DVC pipeline left untouched.
- **No placeholders.** All code shown is the literal replacement.
- **Type consistency:** `balance_reactions(...)` returns `list[tuple[str | None, float | None]]` per `syn_rbl.py:75-78`. The new chunked loop unpacks tuples identically to the old one-shot call (lines 349-358 of the pre-change file).
- **Failure isolation depth:** the wrapper's `try/except` at `syn_rbl.py:110-119` catches *any* exception during `bal.rebalance()` and returns all-`(None, None)`. This is the same isolation the script has been relying on — no new error-handling code is needed in the CLI.
- **Memory:** holding `~1M USPTO rows × (str + bool)` fully in memory is ~few hundred MB. The script writes shards to disk and re-reads them at the end (lower memory peak); the CLI accumulates lists. Acceptable on the user's hardware per prior runs.
- **Out of scope:** atom-count revalidation (handled downstream by `balance_validate`); USPTO stoichiometry recovery (todo.md item, separate work); resume via on-disk shards (explicitly declined).

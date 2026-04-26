from __future__ import annotations

from pathlib import Path

import polars as pl
import typer

from aichemy.config import PreprocessingConfig, load_config
from aichemy.preprocessing import export as export_module
from aichemy.preprocessing.augment import directionality as directionality_module
from aichemy.preprocessing.augment import prices as prices_module
from aichemy.preprocessing.augment import (
    prices_scrapers as _prices_scrapers,  # noqa: F401 — side effect: registers scrapers
)
from aichemy.preprocessing.augment import thermo as thermo_module
from aichemy.preprocessing.augment import yields as yields_module
from aichemy.preprocessing.augment.directionality import DirectionalityMode
from aichemy.preprocessing.balance import validate as balance_validate_module
from aichemy.preprocessing.io import (
    interim_path,
    processed_path,
    raw_path,
    read_molecules,
    read_reactions,
    write_empty_molecules,
    write_empty_reactions,
    write_molecules,
    write_reactions,
)
from aichemy.solver.cli import solver_app

app = typer.Typer(help="AIchemy preprocessing pipeline.", no_args_is_help=True)
ingest_app = typer.Typer(help="Ingest raw data from a source.")
dedup_app = typer.Typer(help="Deduplicate molecules or reactions.")
balance_app = typer.Typer(help="Balance and validate reaction atom counts.")
augment_app = typer.Typer(help="Enrich the merged table with yields, prices, directionality.")
app.add_typer(ingest_app, name="ingest")
app.add_typer(dedup_app, name="dedup")
app.add_typer(balance_app, name="balance")
app.add_typer(augment_app, name="augment")
app.add_typer(solver_app, name="solve")


def _load(config: Path, overrides: list[Path]) -> PreprocessingConfig:
    return load_config(config, overrides)


ConfigOpt = typer.Option(..., "--config", help="Path to base YAML config.")
OverrideOpt = typer.Option(
    [], "--override", help="Override YAML (repeatable; later overrides win)."
)


@app.command("fetch-raw")
def fetch_raw(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Download raw MetaNetX (TSV) and USPTO (7z) source data."""
    from aichemy.preprocessing.sources.fetch import download

    cfg = _load(config, override)
    mnx_dir = raw_path(cfg, "metanetx")
    uspto_dir = raw_path(cfg, "uspto")
    mnx_dir.mkdir(parents=True, exist_ok=True)
    uspto_dir.mkdir(parents=True, exist_ok=True)

    mnx_urls = cfg.sources.metanetx_urls
    mnx_map = {
        "reac_prop.tsv": mnx_urls.reac_prop,
        "chem_prop.tsv": mnx_urls.chem_prop,
        "reac_xref.tsv": mnx_urls.reac_xref,
        "chem_xref.tsv": mnx_urls.chem_xref,
    }
    for filename, url in mnx_map.items():
        download(url, mnx_dir / filename)

    # USPTO: grants by default; full slice pulls both grants + applications.
    uspto_urls = cfg.sources.uspto_urls
    uspto_map = {"grants_smiles.7z": uspto_urls.grants_smiles}
    if cfg.sources.uspto_slice == "full":
        uspto_map["applications_smiles.7z"] = uspto_urls.applications_smiles
    for filename, url in uspto_map.items():
        download(url, uspto_dir / filename)

    typer.echo(
        f"[fetch-raw] MetaNetX ({len(mnx_map)} files) and USPTO ({len(uspto_map)} files) ready."
    )


@ingest_app.command("metanetx")
def ingest_metanetx(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Parse MetaNetX TSVs (reac_prop, chem_prop) into interim parquets."""
    from aichemy.preprocessing.sources import metanetx as metanetx_module

    cfg = _load(config, override)
    raw_dir = raw_path(cfg, "metanetx")
    rxn_out = interim_path(cfg, "metanetx", "reactions_raw.parquet")
    mol_out = interim_path(cfg, "metanetx", "molecules_raw.parquet")

    chem_prop = raw_dir / "chem_prop.tsv"
    reac_prop = raw_dir / "reac_prop.tsv"
    if not (chem_prop.exists() and reac_prop.exists()):
        write_empty_reactions(rxn_out)
        write_empty_molecules(mol_out)
        typer.echo(f"[ingest metanetx] raw TSVs missing at {raw_dir}; wrote empty parquets.")
        return

    molecules, reactions = metanetx_module.ingest_metanetx(raw_dir)
    write_molecules(molecules, mol_out)
    write_reactions(reactions, rxn_out)
    typer.echo(
        f"[ingest metanetx] wrote {molecules.height} molecules, {reactions.height} reactions."
    )


@ingest_app.command("uspto")
def ingest_uspto(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Parse USPTO Lowe .rsmi into interim parquet (extracts 7z if needed)."""
    from aichemy.preprocessing.sources import uspto as uspto_module

    cfg = _load(config, override)
    raw_dir = raw_path(cfg, "uspto")
    rxn_out = interim_path(cfg, "uspto", "reactions_raw.parquet")

    rsmi_path = raw_dir / "1976_Sep2016_USPTOgrants_smiles.rsmi"
    archive_path = raw_dir / "grants_smiles.7z"

    if not rsmi_path.exists() and archive_path.exists():
        import py7zr

        with py7zr.SevenZipFile(archive_path) as z:
            z.extractall(raw_dir)
        typer.echo(f"[ingest uspto] extracted {archive_path} → {raw_dir}")

    if not rsmi_path.exists():
        write_empty_reactions(rxn_out)
        typer.echo(f"[ingest uspto] raw .rsmi missing at {rsmi_path}; wrote empty parquet.")
        return

    reactions = uspto_module.ingest_uspto(rsmi_path)
    write_reactions(reactions, rxn_out)
    typer.echo(f"[ingest uspto] wrote {reactions.height} reactions from {rsmi_path.name}.")


@app.command("normalize")
def normalize(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Merge MetaNetX + USPTO sources, canonicalize, apply hydrocarbon filter."""
    from aichemy.preprocessing import normalize as normalize_module

    cfg = _load(config, override)
    mnx_mol_in = interim_path(cfg, "metanetx", "molecules_raw.parquet")
    mnx_rxn_in = interim_path(cfg, "metanetx", "reactions_raw.parquet")
    uspto_rxn_in = interim_path(cfg, "uspto", "reactions_raw.parquet")
    mol_out = interim_path(cfg, "normalized", "molecules.parquet")
    rxn_out = interim_path(cfg, "normalized", "reactions.parquet")

    if not (mnx_mol_in.exists() and mnx_rxn_in.exists()):
        write_empty_molecules(mol_out)
        write_empty_reactions(rxn_out)
        typer.echo("[normalize] upstream MetaNetX interim missing; wrote empty parquets.")
        return

    mnx_mols = read_molecules(mnx_mol_in)
    mnx_mols = normalize_module.canonicalize_molecules(mnx_mols)

    reactions = read_reactions(mnx_rxn_in)
    if uspto_rxn_in.exists():
        uspto_reactions = read_reactions(uspto_rxn_in)
        reactions = pl.concat([reactions, uspto_reactions], how="diagonal_relaxed")

        # Extract unique molecules from USPTO reactions so their mol_ids
        # resolve during the carbon filter.
        uspto_mols = normalize_module.extract_uspto_molecules(uspto_reactions)
        molecules = normalize_module.merge_sources(mnx_mols, uspto_mols)
    else:
        molecules = mnx_mols

    filtered = normalize_module.filter_reactions_by_carbon(
        reactions, molecules, min_carbon=cfg.filter.min_carbon_count
    )
    molecules = normalize_module.filter_molecules_by_usage(molecules, filtered)

    write_molecules(molecules, mol_out)
    write_reactions(filtered, rxn_out)
    typer.echo(
        f"[normalize] wrote {molecules.height} molecules, {filtered.height} reactions "
        f"(kept {filtered.height} of {reactions.height} after carbon filter)."
    )


@dedup_app.command("molecules")
def dedup_molecules(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Deduplicate molecules (InChIKey primary). Emits dedup_map.json sidecar."""
    import json

    from aichemy.preprocessing.dedup import molecules as dedup_mol_module

    cfg = _load(config, override)
    input_path = interim_path(cfg, "normalized", "molecules.parquet")
    output_path = interim_path(cfg, "deduped", "molecules.parquet")
    map_path = interim_path(cfg, "deduped", "dedup_map.json")

    if not input_path.exists():
        write_empty_molecules(output_path)
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text("{}\n")
        typer.echo(f"[dedup molecules] upstream {input_path} missing; wrote empty parquet.")
        return

    df = read_molecules(input_path)
    if df.height == 0:
        write_empty_molecules(output_path)
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text("{}\n")
        typer.echo("[dedup molecules] input empty; nothing to dedup.")
        return

    deduped, dedup_map = dedup_mol_module.dedup_molecules(df)
    write_molecules(deduped, output_path)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(dedup_map, indent=2, sort_keys=True) + "\n")
    typer.echo(
        f"[dedup molecules] wrote {deduped.height} rows "
        f"(collapsed {df.height - deduped.height}); dedup_map.json sidecar written."
    )


@dedup_app.command("reactions")
def dedup_reactions(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Dedup reactions: rewrite mol_ids via dedup_map, collapse duplicates."""
    import json

    from aichemy.preprocessing.dedup import reactions as dedup_rxn_module

    cfg = _load(config, override)
    reactions_in = interim_path(cfg, "normalized", "reactions.parquet")
    molecules_in = interim_path(cfg, "deduped", "molecules.parquet")
    map_in = interim_path(cfg, "deduped", "dedup_map.json")
    output_path = interim_path(cfg, "deduped", "reactions.parquet")

    if not (reactions_in.exists() and molecules_in.exists()):
        write_empty_reactions(output_path)
        typer.echo("[dedup reactions] upstream missing; wrote empty parquet.")
        return

    reactions = read_reactions(reactions_in)
    molecules = read_molecules(molecules_in)
    dedup_map = json.loads(map_in.read_text()) if map_in.exists() else {}

    if reactions.height == 0:
        write_empty_reactions(output_path)
        typer.echo("[dedup reactions] input empty; nothing to dedup.")
        return

    deduped = dedup_rxn_module.dedup_reactions(reactions, molecules, dedup_map)
    write_reactions(deduped, output_path)
    typer.echo(
        f"[dedup reactions] wrote {deduped.height} rows "
        f"(collapsed {reactions.height - deduped.height})."
    )


@balance_app.command("uspto")
def balance_uspto(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
    chunk_size: int = typer.Option(
        5000,
        "--chunk-size",
        help="USPTO rows per SYN-RBL batch. Smaller = less data lost per crash, "
        "more SYN-RBL init overhead.",
    ),
    workers: int = typer.Option(
        -1,
        "--workers",
        help="n_jobs forwarded to SYN-RBL (-1 = all cores).",
    ),
) -> None:
    """Run SYN-RBL atom-balancing on USPTO reactions; MetaNetX rows pass through.

    Chunked: USPTO rows go through SYN-RBL in batches of --chunk-size with
    n_jobs=--workers per batch. A crash inside a batch is contained by the
    wrapper (returns all-unbalanced for that batch) and the loop continues.
    No on-disk checkpointing — interrupting discards in-memory progress.
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
        # Only MetaNetX rows present — pass through unchanged.
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

    new_smiles_all: list[str | None] = []
    balanced_all: list[bool] = []
    overall_start = time.time()

    for chunk_idx in range(n_chunks):
        start = chunk_idx * chunk_size
        end = min(start + chunk_size, uspto_count)
        chunk_smiles = orig_smiles_all[start:end]

        t0 = time.time()
        results = syn_rbl_module.balance_reactions(chunk_smiles, n_jobs=workers)
        elapsed = time.time() - t0

        # Gate: balanced=True iff SYN-RBL emitted a SMILES AND
        # (confidence is None — deterministic solve — OR confidence > threshold).
        # When the gate fails, preserve the original USPTO SMILES so downstream
        # stages still see the patent claim.
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


@balance_app.command("validate")
def balance_validate(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Universal atom-count validation; populates balanced: bool for all reactions."""
    cfg = _load(config, override)
    input_path = interim_path(cfg, "balanced", "reactions.parquet")
    output_path = interim_path(cfg, "validated", "reactions.parquet")

    if not input_path.exists():
        write_empty_reactions(output_path)
        typer.echo(f"[balance validate] upstream {input_path} missing; wrote empty parquet.")
        return

    df = read_reactions(input_path)
    mol_path = interim_path(cfg, "deduped", "molecules.parquet")
    molecules = read_molecules(mol_path) if mol_path.exists() else None
    # MetaNetX frequently elides protons — tell the validator to ignore H
    # imbalance so those reactions aren't all flagged as unbalanced.
    validated = balance_validate_module.validate_reactions(
        df, molecules=molecules, ignore_elements=["H"]
    )
    write_reactions(validated, output_path)
    typer.echo(
        f"[balance validate] wrote {validated.height} rows "
        f"({validated.filter(validated['balanced']).height} balanced)."
    )


@augment_app.command("yields")
def augment_yields(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Fill missing yield_rate per configured strategy."""
    cfg = _load(config, override)
    input_path = interim_path(cfg, "validated", "reactions.parquet")
    output_path = interim_path(cfg, "augmented", "reactions_yields.parquet")

    if not input_path.exists():
        write_empty_reactions(output_path)
        typer.echo(f"[augment yields] upstream {input_path} missing; wrote empty parquet.")
        return

    df = read_reactions(input_path)
    augmented = yields_module.augment_yields(df, cfg.yields)
    write_reactions(augmented, output_path)
    typer.echo(f"[augment yields] wrote {augmented.height} rows (strategy={cfg.yields.strategy}).")


@augment_app.command("prices")
def augment_prices(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Populate price_per_gram via configured PriceLookup backend."""
    cfg = _load(config, override)
    input_path = interim_path(cfg, "deduped", "molecules.parquet")
    output_path = interim_path(cfg, "augmented", "molecules_priced.parquet")

    if not input_path.exists():
        # Upstream stage hasn't produced input yet — keep behavior stub-compatible
        # so dvc repro on the bare pipeline stays green.
        write_empty_molecules(output_path)
        typer.echo(f"[augment prices] upstream {input_path} missing; wrote empty parquet.")
        return

    lookup = prices_module.make_lookup(cfg)
    molecules = read_molecules(input_path)
    priced = prices_module.augment_prices(molecules, lookup)
    write_molecules(priced, output_path)
    typer.echo(
        f"[augment prices] wrote {priced.height} rows to {output_path} "
        f"(backend={cfg.prices.backend})."
    )


@augment_app.command("thermo")
def augment_thermo(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
    skip: bool = typer.Option(
        False, "--skip", help="Bypass the whole step (pass input through unchanged)."
    ),
    skip_uspto: bool = typer.Option(
        False, "--skip-uspto", help="Leave USPTO rows with delta_g=null (no Tier 2 attempt)."
    ),
) -> None:
    """Populate delta_g (ΔG'°) via eQuilibrator on MetaNetX reactions."""
    cfg = _load(config, override)
    input_path = interim_path(cfg, "augmented", "reactions_yields.parquet")
    molecules_path = interim_path(cfg, "deduped", "molecules.parquet")
    output_path = interim_path(cfg, "augmented", "reactions_thermo.parquet")

    if not input_path.exists():
        write_empty_reactions(output_path)
        typer.echo(f"[augment thermo] upstream {input_path} missing; wrote empty parquet.")
        return

    if skip or not thermo_module.is_available():
        import shutil

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(input_path, output_path)
        reason = (
            "--skip flag set"
            if skip
            else "equilibrator-api not installed (install with `uv sync --extra thermo`)"
        )
        typer.echo(f"[augment thermo] {reason}; passing through {input_path} unchanged.")
        return

    df = read_reactions(input_path)
    molecules = read_molecules(molecules_path) if molecules_path.exists() else None
    skip_sources = {"uspto"} if skip_uspto else None
    augmented = thermo_module.augment_thermo(df, molecules=molecules, skip_sources=skip_sources)
    write_reactions(augmented, output_path)
    resolved = augmented.filter(pl.col("delta_g").is_not_null()).height
    typer.echo(
        f"[augment thermo] wrote {augmented.height} rows "
        f"({resolved} with computed ΔG'°; the rest couldn't be resolved against "
        "eQuilibrator's compound catalog)."
    )


@augment_app.command("directionality")
def augment_directionality(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Apply MetaNetX directionality flag (annotate or duplicate reversibles)."""
    cfg = _load(config, override)
    input_path = interim_path(cfg, "augmented", "reactions_thermo.parquet")
    output_path = interim_path(cfg, "augmented", "reactions_full.parquet")

    if not input_path.exists():
        write_empty_reactions(output_path)
        typer.echo(f"[augment directionality] upstream {input_path} missing; wrote empty parquet.")
        return

    df = read_reactions(input_path)
    if "direction" in df.columns:
        augmented = directionality_module.apply_directionality(df, mode=DirectionalityMode.ANNOTATE)
    else:
        augmented = df  # nothing to do without direction annotation
    write_reactions(augmented, output_path)
    typer.echo(f"[augment directionality] wrote {augmented.height} rows.")


@app.command("export")
def export(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Write final unified hypergraph parquets + manifest.json to data/processed/."""
    cfg = _load(config, override)
    reactions_in = interim_path(cfg, "augmented", "reactions_full.parquet")
    molecules_in = interim_path(cfg, "augmented", "molecules_priced.parquet")
    reactions_out = processed_path(cfg, "reactions.parquet")
    molecules_out = processed_path(cfg, "molecules.parquet")
    manifest_out = processed_path(cfg, "hypergraph_manifest.json")

    if not (reactions_in.exists() and molecules_in.exists()):
        # Upstream missing — stay stub-compatible for a clean dvc repro on
        # a bare pipeline, but still emit the manifest so downstream tooling
        # always has a summary to read.
        write_empty_reactions(reactions_out)
        write_empty_molecules(molecules_out)
        export_module.write_manifest(
            read_reactions(reactions_out),
            read_molecules(molecules_out),
            metanetx_version=cfg.sources.metanetx_version,
            uspto_slice=cfg.sources.uspto_slice,
            output_path=manifest_out,
        )
        typer.echo(f"[export] upstream missing; wrote empty parquets + manifest to {manifest_out}.")
        return

    reactions = read_reactions(reactions_in)
    molecules = read_molecules(molecules_in)

    # Only enforce referential integrity when there is something to check.
    if reactions.height > 0:
        export_module.assert_referential_integrity(reactions, molecules)

    write_reactions(reactions, reactions_out)
    write_molecules(molecules, molecules_out)
    export_module.write_manifest(
        reactions,
        molecules,
        metanetx_version=cfg.sources.metanetx_version,
        uspto_slice=cfg.sources.uspto_slice,
        output_path=manifest_out,
    )
    typer.echo(
        f"[export] wrote {reactions.height} reactions, {molecules.height} molecules, "
        f"manifest -> {manifest_out}."
    )


if __name__ == "__main__":
    app()

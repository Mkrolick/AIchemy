from __future__ import annotations

from pathlib import Path

import typer

from aichemy.config import PreprocessingConfig, load_config
from aichemy.preprocessing.augment import prices as prices_module
from aichemy.preprocessing.augment import (
    prices_scrapers as _prices_scrapers,  # noqa: F401 — side effect: registers scrapers
)
from aichemy.preprocessing.io import (
    interim_path,
    processed_path,
    raw_path,
    read_molecules,
    write_empty_molecules,
    write_empty_reactions,
    write_molecules,
)

app = typer.Typer(help="AIchemy preprocessing pipeline.", no_args_is_help=True)
ingest_app = typer.Typer(help="Ingest raw data from a source.")
dedup_app = typer.Typer(help="Deduplicate molecules or reactions.")
balance_app = typer.Typer(help="Balance and validate reaction atom counts.")
augment_app = typer.Typer(help="Enrich the merged table with yields, prices, directionality.")
app.add_typer(ingest_app, name="ingest")
app.add_typer(dedup_app, name="dedup")
app.add_typer(balance_app, name="balance")
app.add_typer(augment_app, name="augment")


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
    """Download raw MetaNetX and USPTO source data. STUB: creates empty dirs."""
    cfg = _load(config, override)
    raw_path(cfg, "metanetx").mkdir(parents=True, exist_ok=True)
    raw_path(cfg, "uspto").mkdir(parents=True, exist_ok=True)
    typer.echo("[STUB] fetch-raw: created raw/metanetx and raw/uspto directories.")


@ingest_app.command("metanetx")
def ingest_metanetx(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Parse MetaNetX TSVs to interim parquet. STUB: empty parquets."""
    cfg = _load(config, override)
    write_empty_reactions(interim_path(cfg, "metanetx", "reactions_raw.parquet"))
    write_empty_molecules(interim_path(cfg, "metanetx", "molecules_raw.parquet"))
    typer.echo("[STUB] ingest metanetx: wrote empty interim parquets.")


@ingest_app.command("uspto")
def ingest_uspto(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Parse USPTO reaction SMILES to interim parquet. STUB: empty parquet."""
    cfg = _load(config, override)
    write_empty_reactions(interim_path(cfg, "uspto", "reactions_raw.parquet"))
    typer.echo("[STUB] ingest uspto: wrote empty interim parquet.")


@app.command("normalize")
def normalize(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Merge sources, canonicalize SMILES, apply hydrocarbon filter. STUB."""
    cfg = _load(config, override)
    write_empty_reactions(interim_path(cfg, "normalized", "reactions.parquet"))
    write_empty_molecules(interim_path(cfg, "normalized", "molecules.parquet"))
    typer.echo("[STUB] normalize: wrote empty normalized parquets.")


@dedup_app.command("molecules")
def dedup_molecules(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Deduplicate molecules (InChIKey primary, Tanimoto secondary). STUB."""
    cfg = _load(config, override)
    write_empty_molecules(interim_path(cfg, "deduped", "molecules.parquet"))
    typer.echo("[STUB] dedup molecules: wrote empty deduped parquet.")


@dedup_app.command("reactions")
def dedup_reactions(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Deduplicate reactions; rewrite mol_ids via dedup_map. STUB."""
    cfg = _load(config, override)
    write_empty_reactions(interim_path(cfg, "deduped", "reactions.parquet"))
    typer.echo("[STUB] dedup reactions: wrote empty deduped parquet.")


@balance_app.command("uspto")
def balance_uspto(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """SYN-RBL atom-mapping for USPTO reactions. STUB."""
    cfg = _load(config, override)
    write_empty_reactions(interim_path(cfg, "balanced", "reactions.parquet"))
    typer.echo("[STUB] balance uspto: wrote empty balanced parquet.")


@balance_app.command("validate")
def balance_validate(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Universal atom-count validation; populates balanced: bool. STUB."""
    cfg = _load(config, override)
    write_empty_reactions(interim_path(cfg, "validated", "reactions.parquet"))
    typer.echo("[STUB] balance validate: wrote empty validated parquet.")


@augment_app.command("yields")
def augment_yields(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Fill missing yields per configured strategy. STUB."""
    cfg = _load(config, override)
    write_empty_reactions(interim_path(cfg, "augmented", "reactions_yields.parquet"))
    typer.echo("[STUB] augment yields: wrote empty parquet.")


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


@augment_app.command("directionality")
def augment_directionality(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Apply MetaNetX directionality flag (forward-only reactions). STUB."""
    cfg = _load(config, override)
    write_empty_reactions(interim_path(cfg, "augmented", "reactions_full.parquet"))
    typer.echo("[STUB] augment directionality: wrote empty parquet.")


@app.command("export")
def export(
    config: Path = ConfigOpt,
    override: list[Path] = OverrideOpt,
) -> None:
    """Write final unified hypergraph parquets to data/processed/. STUB."""
    cfg = _load(config, override)
    write_empty_reactions(processed_path(cfg, "reactions.parquet"))
    write_empty_molecules(processed_path(cfg, "molecules.parquet"))
    typer.echo("[STUB] export: wrote empty processed parquets.")


if __name__ == "__main__":
    app()

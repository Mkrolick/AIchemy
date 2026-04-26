from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class DedupConfig(BaseModel):
    model_config = {"extra": "forbid"}

    tanimoto_threshold: float = 1.0
    reaction_tanimoto_threshold: float = 0.95
    fingerprint_radius: int = 2
    fingerprint_bits: int = 2048


class FilterConfig(BaseModel):
    model_config = {"extra": "forbid"}

    min_carbon_count: int = 2


class YieldImputationStrategy(StrEnum):
    GLOBAL_MEAN = "global_mean"
    PER_EC_CLASS = "per_ec_class"
    FIXED = "fixed"


class YieldConfig(BaseModel):
    model_config = {"extra": "forbid"}

    strategy: YieldImputationStrategy = YieldImputationStrategy.GLOBAL_MEAN
    fixed_value: float = 0.85
    enzymatic_prior_range: tuple[float, float] = (0.85, 0.95)


class LicensesConfig(BaseModel):
    model_config = {"extra": "forbid"}

    patentsview_endpoint: str = "https://search.patentsview.org/api/v1/patent"
    cpc_rules_path: Path = Field(default_factory=lambda: Path("configs/cpc_rules.yaml"))
    cache_path: Path = Field(default_factory=lambda: Path("data/interim/licenses/llm_cache.jsonl"))
    llm_model: str = "claude-haiku-4-5"
    fetch_batch_size: int = 25
    fetch_max_retries: int = 3
    llm_max_retries: int = 3


class MetaNetXURLsConfig(BaseModel):
    model_config = {"extra": "forbid"}

    reac_prop: str = "https://www.metanetx.org/ftp/4.4/reac_prop.tsv"
    chem_prop: str = "https://www.metanetx.org/ftp/4.4/chem_prop.tsv"
    reac_xref: str = "https://www.metanetx.org/ftp/4.4/reac_xref.tsv"
    chem_xref: str = "https://www.metanetx.org/ftp/4.4/chem_xref.tsv"


class USPTOURLsConfig(BaseModel):
    model_config = {"extra": "forbid"}

    # Lowe 1976-Sep2016 grants reaction SMILES (75MB 7z from figshare).
    grants_smiles: str = "https://ndownloader.figshare.com/files/8664379"
    # Lowe 2001-Sep2016 applications reaction SMILES (87MB 7z).
    applications_smiles: str = "https://ndownloader.figshare.com/files/8664370"


class SourcesConfig(BaseModel):
    model_config = {"extra": "forbid"}

    metanetx_version: str = "4.4"
    uspto_slice: Literal["grants_1976_2016", "full"] = "grants_1976_2016"
    metanetx_urls: MetaNetXURLsConfig = Field(default_factory=MetaNetXURLsConfig)
    uspto_urls: USPTOURLsConfig = Field(default_factory=USPTOURLsConfig)


class PubChemConfig(BaseModel):
    model_config = {"extra": "forbid"}

    enabled: bool = True
    rate_limit_seconds: float = 0.25  # PubChem allows ~5 req/s
    timeout_seconds: float = 10.0


class ScraperVendorConfig(BaseModel):
    model_config = {"extra": "forbid"}

    name: str  # identifier (e.g. "chemicalbook", "benchchem")
    enabled: bool = False
    rate_limit_seconds: float = 5.0


class ScraperConfig(BaseModel):
    model_config = {"extra": "forbid"}

    enabled: bool = False  # master switch — scraping is off unless explicitly enabled
    vendors: list[ScraperVendorConfig] = Field(default_factory=list)
    user_agent: str = (
        "AIchemy-research/0.1 (https://github.com/mkrolick/AIchemy; malcolm.krolick@gmail.com)"
    )
    respect_robots_txt: bool = True
    cache_path: Path = Field(default_factory=lambda: Path("data/interim/scraper_cache.sqlite"))
    max_retries: int = 3
    backoff_base_seconds: float = 2.0


class AichemyPricingConfig(BaseModel):
    """Backend-specific config for the standalone `aichemy_pricing` package.

    Path fields point at the offline catalog (PubChem SDF dir + a SQLite cache
    location). `allowed_sources` filters the in-memory InChIKey index to a
    vendor allowlist — REQUIRED for full-scale runs (491M SIDs OOM otherwise;
    see `aichemy_pricing.resolvers.pubchem_sdf` docstring). `max_workers`
    controls the `augment_prices` thread pool size (1 = today's serial
    behavior; 100 ~ master-plan target wall-clock for 100K compounds).
    """

    model_config = {"extra": "forbid"}

    catalog_dir: Path = Field(default_factory=lambda: Path("data/raw/pubchem_substance"))
    cache_path: Path = Field(
        default_factory=lambda: Path("data/interim/aichemy_pricing_cache.sqlite")
    )
    allowed_sources: list[str] | None = None
    max_workers: int = Field(default=1, ge=1)


class PricesConfig(BaseModel):
    model_config = {"extra": "forbid"}

    backend: Literal["stub", "chained", "aichemy_pricing"] = "chained"
    chain: list[str] = Field(default_factory=lambda: ["curated", "pubchem"])
    cache_path: Path = Field(default_factory=lambda: Path("data/interim/prices_cache.sqlite"))
    cache_ttl_days: int = 30
    pubchem: PubChemConfig = Field(default_factory=PubChemConfig)
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    aichemy_pricing: AichemyPricingConfig = Field(default_factory=AichemyPricingConfig)


class PathsConfig(BaseModel):
    model_config = {"extra": "forbid"}

    data_dir: Path = Field(default_factory=lambda: Path("data"))


class PreprocessingConfig(BaseModel):
    model_config = {"extra": "forbid"}

    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    filter: FilterConfig = Field(default_factory=FilterConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    yields: YieldConfig = Field(default_factory=YieldConfig)
    prices: PricesConfig = Field(default_factory=PricesConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    licenses: LicensesConfig = Field(default_factory=LicensesConfig)


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-merge override into base.

    Dict-valued keys: recursively merged.
    All other types (scalars, lists, tuples): replaced wholesale.
    Returns a new dict; does not mutate inputs.
    """
    out = dict(base)
    for key, override_val in override.items():
        base_val = out.get(key)
        if isinstance(base_val, dict) and isinstance(override_val, Mapping):
            out[key] = _deep_merge(base_val, override_val)
        else:
            out[key] = override_val
    return out


def load_config(
    path: Path,
    overrides: Iterable[Path] = (),
) -> PreprocessingConfig:
    """Load base YAML, deep-merge each override in order, validate via Pydantic."""
    with open(path) as f:
        merged: dict[str, Any] = yaml.safe_load(f) or {}
    for override_path in overrides:
        with open(override_path) as f:
            override: dict[str, Any] = yaml.safe_load(f) or {}
        merged = _deep_merge(merged, override)
    return PreprocessingConfig.model_validate(merged)

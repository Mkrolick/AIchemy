"""ASKCOS buyables catalog (https://github.com/ASKCOS/askcos-data).

A 280k-entry JSON list of commercially available chemicals with per-gram
USD prices, aggregated by MIT from three supplier feeds:

    - EM (eMolecules), 103k rows
    - LN (LabNetwork / Sigma-Aldrich subset), 157k rows
    - SA (Sigma-Aldrich core catalog), 20k rows

Prices are ``ppg`` (USD per gram) as surfaced by ASKCOS's buyability
heuristic — values are capped to [1, 100] to express buy-tier, not
absolute price. Good enough as a seed catalog for MILP cost coefficients
where we need SOME real price on every commodity reagent.

Canonicalizes SMILES with RDKit on load so lookups tolerate the usual
aromatization / tautomer / stereo normalization drift. A parquet
sidecar (``buyables.canonical.parquet``) is generated next to the gz on
first use and reused thereafter — canonicalizing 280k SMILES cold costs
~30s and we don't want to pay that on every import.
"""

from __future__ import annotations

import gzip
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
from rdkit import Chem, RDLogger

from aichemy.scrapers.prices.base import PriceQuote, PriceScraperBase
from aichemy.scrapers.prices.registry import register_scraper

log = logging.getLogger(__name__)

DEFAULT_BUYABLES_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "external" / "askcos" / "buyables.json.gz"
)
SOURCE_URL = "https://github.com/ASKCOS/askcos-data/blob/main/buyables/buyables.json.gz"


@dataclass(frozen=True)
class AskcosEntry:
    canonical_smiles: str
    ppg_usd: float
    source: str
    raw_smiles: str


class AskcosCatalog:
    """In-memory lookup over the ASKCOS buyables catalog.

    Load cost: ~30s cold (RDKit canonicalization of 280k SMILES), <1s
    warm (parquet sidecar hit).
    """

    def __init__(self, gz_path: Path | None = None) -> None:
        self._gz_path = gz_path or DEFAULT_BUYABLES_PATH
        self._by_canon: dict[str, AskcosEntry] = {}
        self._load()

    @property
    def size(self) -> int:
        return len(self._by_canon)

    def lookup(self, canonical_smiles: str) -> AskcosEntry | None:
        return self._by_canon.get(canonical_smiles)

    def _load(self) -> None:
        parquet_path = self._gz_path.with_suffix("").with_suffix(".canonical.parquet")
        if parquet_path.exists() and parquet_path.stat().st_mtime > self._gz_path.stat().st_mtime:
            log.info("AskcosCatalog: reading cached canonical parquet at %s", parquet_path)
            df = pl.read_parquet(parquet_path)
            for row in df.iter_rows(named=True):
                self._by_canon[row["canonical_smiles"]] = AskcosEntry(
                    canonical_smiles=row["canonical_smiles"],
                    ppg_usd=float(row["ppg_usd"]),
                    source=row["source"],
                    raw_smiles=row["raw_smiles"],
                )
            return

        log.info("AskcosCatalog: loading raw buyables from %s", self._gz_path)
        with gzip.open(self._gz_path, "rt") as f:
            raw = json.load(f)
        log.info("AskcosCatalog: canonicalizing %d SMILES (cold path)...", len(raw))

        RDLogger.DisableLog("rdApp.*")  # type: ignore[attr-defined]
        try:
            for row in raw:
                smi = row.get("smiles")
                ppg = row.get("ppg")
                if not smi or ppg is None:
                    continue
                mol = Chem.MolFromSmiles(smi)
                if mol is None:
                    continue
                canon = Chem.MolToSmiles(mol, canonical=True)
                # Keep cheapest price per canonical SMILES (multiple suppliers).
                existing = self._by_canon.get(canon)
                if existing is None or float(ppg) < existing.ppg_usd:
                    self._by_canon[canon] = AskcosEntry(
                        canonical_smiles=canon,
                        ppg_usd=float(ppg),
                        source=row.get("source", ""),
                        raw_smiles=smi,
                    )
        finally:
            RDLogger.EnableLog("rdApp.*")  # type: ignore[attr-defined]

        log.info(
            "AskcosCatalog: loaded %d unique canonical SMILES from %d raw rows",
            len(self._by_canon),
            len(raw),
        )

        df = pl.DataFrame(
            [
                {
                    "canonical_smiles": e.canonical_smiles,
                    "ppg_usd": e.ppg_usd,
                    "source": e.source,
                    "raw_smiles": e.raw_smiles,
                }
                for e in self._by_canon.values()
            ]
        )
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(parquet_path)
        log.info("AskcosCatalog: wrote canonical sidecar to %s", parquet_path)


class AskcosScraper(PriceScraperBase):
    """``PriceScraperBase`` adapter for the local ASKCOS catalog.

    Not a scraper in the network sense — it's a constant-time in-memory
    lookup — but wrapping it as a scraper lets the existing pipeline and
    cache write it with source-URL provenance just like any other vendor.
    """

    vendor_name = "askcos"

    def __init__(self, **kwargs: Any) -> None:
        # rate_limit_seconds / robots don't apply; override defaults so the
        # base class's httpx client is still created (harmless, never used)
        # without emitting warnings about robots.txt.
        kwargs.setdefault("rate_limit_seconds", 0.0)
        kwargs.setdefault("respect_robots_txt", False)
        super().__init__(**kwargs)
        self._catalog = AskcosCatalog()

    def _fetch_quote(self, smiles: str) -> PriceQuote | None:
        if not smiles:
            return None
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        canon = Chem.MolToSmiles(mol, canonical=True)
        entry = self._catalog.lookup(canon)
        if entry is None:
            return None
        return PriceQuote(
            smiles=canon,
            price_per_gram_usd=entry.ppg_usd,
            vendor=self.vendor_name,
            source_url=SOURCE_URL,
            fetched_at=datetime.now(UTC),
            extra={"askcos_source": entry.source, "raw_smiles": entry.raw_smiles},
        )


def _factory(**kwargs: Any) -> AskcosScraper:
    return AskcosScraper(**kwargs)


register_scraper("askcos", _factory)

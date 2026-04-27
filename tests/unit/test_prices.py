from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from aichemy.config import PreprocessingConfig
from aichemy.preprocessing.augment.prices import (
    CachedPriceLookup,
    ChainedPriceLookup,
    PriceLookup,
    PubChemClient,
    ScraperBase,
    StubPriceLookup,
    make_lookup,
)

# ---------- Stub -------------------------------------------------------------


def test_stub_price_lookup_returns_none_by_default() -> None:
    lookup: PriceLookup = StubPriceLookup()
    assert lookup.lookup("CCO") is None


def test_stub_price_lookup_returns_preloaded_value() -> None:
    lookup = StubPriceLookup({"CCO": 1.23})
    assert lookup.lookup("CCO") == 1.23
    assert lookup.lookup("CCN") is None


# ---------- Chain ------------------------------------------------------------


def test_chain_returns_first_non_none_result() -> None:
    first = StubPriceLookup({})  # always None
    second = StubPriceLookup({"CCO": 2.5})
    third = StubPriceLookup({"CCO": 9.9})  # should not be reached
    chain = ChainedPriceLookup([first, second, third])
    assert chain.lookup("CCO") == 2.5


def test_chain_returns_none_when_no_source_has_hit() -> None:
    chain = ChainedPriceLookup([StubPriceLookup(), StubPriceLookup()])
    assert chain.lookup("CCO") is None


def test_chain_survives_failing_inner_source() -> None:
    class _RaisesAlways:
        def lookup(self, smiles: str) -> float | None:
            raise RuntimeError("boom")

    chain = ChainedPriceLookup([_RaisesAlways(), StubPriceLookup({"CCO": 1.0})])
    assert chain.lookup("CCO") == 1.0


# ---------- Cache ------------------------------------------------------------


class _CountingLookup:
    """Inner lookup that counts how many times its lookup() is called."""

    def __init__(self, prices: dict[str, float]) -> None:
        self._prices = prices
        self.call_count = 0

    def lookup(self, smiles: str) -> float | None:
        self.call_count += 1
        return self._prices.get(smiles)


def test_cache_hit_does_not_call_inner_again(tmp_path: Path) -> None:
    inner = _CountingLookup({"CCO": 1.0})
    cache = CachedPriceLookup(inner, cache_path=tmp_path / "c.sqlite", ttl_days=30)
    assert cache.lookup("CCO") == 1.0
    assert cache.lookup("CCO") == 1.0  # second call served from cache
    assert inner.call_count == 1
    cache.close()


def test_cache_caches_misses_too(tmp_path: Path) -> None:
    inner = _CountingLookup({})  # always None
    cache = CachedPriceLookup(inner, cache_path=tmp_path / "c.sqlite", ttl_days=30)
    assert cache.lookup("CCN") is None
    assert cache.lookup("CCN") is None
    assert inner.call_count == 1  # miss was cached, no re-query
    cache.close()


def test_cache_ttl_expiry_forces_refresh(tmp_path: Path) -> None:
    inner = _CountingLookup({"CCO": 1.0})
    cache = CachedPriceLookup(inner, cache_path=tmp_path / "c.sqlite", ttl_days=0)
    cache.lookup("CCO")
    cache.lookup("CCO")  # ttl_days=0 → immediately expired, refreshes
    assert inner.call_count == 2
    cache.close()


# ---------- PubChem ----------------------------------------------------------


def test_pubchem_lookup_always_returns_none() -> None:
    """PubChem does not expose per-gram prices; lookup is a chain-friendly no-op."""
    client = PubChemClient(rate_limit_seconds=0.0)
    # No HTTP mocked; lookup shouldn't touch the network either way.
    assert client.lookup("CCO") is None


def test_pubchem_find_vendors_parses_cid_and_sources(httpx_mock: HTTPXMock) -> None:
    # First call: SMILES → CID
    httpx_mock.add_response(
        url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/CCO/cids/JSON",
        json={"IdentifierList": {"CID": [702]}},
    )
    # Second call: CID → vendor cross-refs
    httpx_mock.add_response(
        url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/702/xrefs/SourceName/JSON",
        json={
            "InformationList": {
                "Information": [{"SourceName": ["Sigma-Aldrich", "TCI", "Alfa Aesar"]}]
            }
        },
    )
    client = PubChemClient(rate_limit_seconds=0.0)
    vendors = client.find_vendors("CCO")
    assert {v.vendor for v in vendors} == {"Sigma-Aldrich", "TCI", "Alfa Aesar"}


def test_pubchem_find_vendors_returns_empty_when_no_cid(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/ZZZZ/cids/JSON",
        status_code=404,
    )
    client = PubChemClient(rate_limit_seconds=0.0)
    assert client.find_vendors("ZZZZ") == []


# ---------- Scraper base (construction guard) -------------------------------


def test_scraper_refuses_to_construct_when_vendor_disabled() -> None:
    from aichemy.config import ScraperVendorConfig

    class DummyScraper(ScraperBase):
        vendor_name = "dummy"

        def _fetch_price(self, smiles: str) -> float | None:
            return None

    with pytest.raises(RuntimeError, match="enabled is False"):
        DummyScraper(
            vendor_config=ScraperVendorConfig(name="dummy", enabled=False),
            user_agent="test-agent",
        )


def test_scraper_rate_limits_between_requests(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    from aichemy.config import ScraperVendorConfig

    class DummyScraper(ScraperBase):
        vendor_name = "dummy"

        def _fetch_price(self, smiles: str) -> float | None:
            resp = self._get("https://example.com/page")
            if resp is None or resp.status_code != 200:
                return None
            return 1.23

    httpx_mock.add_response(url="https://example.com/robots.txt", text="User-agent: *\nAllow: /")
    httpx_mock.add_response(url="https://example.com/page", text="<html>fake</html>")
    scraper = DummyScraper(
        vendor_config=ScraperVendorConfig(name="dummy", enabled=True, rate_limit_seconds=0.0),
        user_agent="test-agent",
        respect_robots_txt=True,
    )
    assert scraper.lookup("CCO") == 1.23


def test_scraper_respects_robots_txt_disallow(
    httpx_mock: HTTPXMock,
) -> None:
    from aichemy.config import ScraperVendorConfig

    class DummyScraper(ScraperBase):
        vendor_name = "dummy"

        def _fetch_price(self, smiles: str) -> float | None:
            resp = self._get("https://example.com/secret")
            return None if resp is None else 9.99

    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nDisallow: /secret\n",
    )
    scraper = DummyScraper(
        vendor_config=ScraperVendorConfig(name="dummy", enabled=True, rate_limit_seconds=0.0),
        user_agent="test-agent",
        respect_robots_txt=True,
    )
    assert scraper.lookup("CCO") is None


# ---------- Factory ----------------------------------------------------------


def test_make_lookup_stub_backend() -> None:
    cfg = PreprocessingConfig()
    cfg.prices.backend = "stub"
    lookup = make_lookup(cfg)
    assert isinstance(lookup, StubPriceLookup)


def test_make_lookup_chained_with_pubchem(tmp_path: Path) -> None:
    cfg = PreprocessingConfig()
    cfg.prices.backend = "chained"
    cfg.prices.chain = ["pubchem"]
    cfg.prices.cache_path = tmp_path / "pc.sqlite"
    lookup = make_lookup(cfg)
    assert isinstance(lookup, CachedPriceLookup)


def test_make_lookup_skips_scraper_when_disabled(tmp_path: Path) -> None:
    cfg = PreprocessingConfig()
    cfg.prices.backend = "chained"
    cfg.prices.chain = ["scraper"]
    cfg.prices.cache_path = tmp_path / "s.sqlite"
    cfg.prices.scraper.enabled = False
    lookup = make_lookup(cfg)
    # Chain has 0 backends; lookup is still valid but always returns None.
    assert lookup.lookup("CCO") is None


# ---------- JSON-LD extraction ----------------------------------------------


def test_jsonld_extractor_finds_product_offer_price() -> None:
    from aichemy.preprocessing.augment.prices_scrapers import (
        StructuredDataPriceScraper,
    )

    html = """
    <html><head>
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Product",
     "name": "Ethanol", "offers": {"@type": "Offer",
     "price": "12.34", "priceCurrency": "USD"}}
    </script></head></html>
    """
    price = StructuredDataPriceScraper._extract_price_from_html(html)
    assert price == 12.34


def test_jsonld_extractor_finds_aggregate_offer() -> None:
    from aichemy.preprocessing.augment.prices_scrapers import (
        StructuredDataPriceScraper,
    )

    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"X",
     "offers":{"@type":"AggregateOffer","lowPrice":"5.0","priceCurrency":"USD"}}
    </script>
    """
    price = StructuredDataPriceScraper._extract_price_from_html(html)
    assert price == 5.0


def test_jsonld_extractor_ignores_non_usd() -> None:
    from aichemy.preprocessing.augment.prices_scrapers import (
        StructuredDataPriceScraper,
    )

    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","offers":
     {"@type":"Offer","price":"99","priceCurrency":"EUR"}}
    </script>
    """
    assert StructuredDataPriceScraper._extract_price_from_html(html) is None


def test_jsonld_extractor_returns_none_when_no_script() -> None:
    from aichemy.preprocessing.augment.prices_scrapers import (
        StructuredDataPriceScraper,
    )

    assert StructuredDataPriceScraper._extract_price_from_html("<html></html>") is None


# ---------- End-to-end scraper with mocked HTTP ------------------------------


def test_structured_scraper_end_to_end(httpx_mock: HTTPXMock) -> None:
    from aichemy.config import ScraperVendorConfig
    from aichemy.preprocessing.augment.prices_scrapers import (
        StructuredDataPriceScraper,
    )

    httpx_mock.add_response(
        url="https://vendor.test/robots.txt",
        text="User-agent: *\nAllow: /\n",
    )
    httpx_mock.add_response(
        url="https://vendor.test/search?q=CCO",
        text=(
            '<script type="application/ld+json">'
            '{"@type":"Product","offers":{"@type":"Offer","price":"42.0",'
            '"priceCurrency":"USD"}}'
            "</script>"
        ),
    )

    scraper = StructuredDataPriceScraper(
        vendor_config=ScraperVendorConfig(name="vendortest", enabled=True, rate_limit_seconds=0.0),
        user_agent="test-agent",
        search_url_template="https://vendor.test/search?q={query}",
        respect_robots_txt=True,
    )
    assert scraper.lookup("CCO") == 42.0


# ---------- Orchestrator: augment_prices on a DataFrame ---------------------


def test_augment_prices_populates_column() -> None:
    import polars as pl

    from aichemy.preprocessing.augment.prices import augment_prices

    df = pl.DataFrame(
        {
            "mol_id": ["A", "B", "C"],
            "canonical_smiles": ["CCO", "CCN", "CCC"],
        }
    )
    lookup = StubPriceLookup({"CCO": 1.0, "CCC": 3.0})
    out = augment_prices(df, lookup)
    prices = dict(zip(out["mol_id"].to_list(), out["price_per_gram"].to_list(), strict=True))
    assert prices == {"A": 1.0, "B": None, "C": 3.0}


def test_augment_prices_requires_canonical_smiles() -> None:
    import polars as pl

    from aichemy.preprocessing.augment.prices import augment_prices

    df = pl.DataFrame({"mol_id": ["A"]})
    with pytest.raises(ValueError, match="canonical_smiles"):
        augment_prices(df, StubPriceLookup())


@pytest.mark.parametrize(
    ("config_value", "expected_kwarg"),
    [
        pytest.param(
            ["Fluorochem", "Enamine"],
            {"Fluorochem", "Enamine"},
            id="populated-list-becomes-set",
        ),
        pytest.param(None, None, id="none-passes-through-as-none"),
        pytest.param([], set(), id="empty-list-becomes-empty-set"),
    ],
)
def test_make_lookup_aichemy_pricing_passes_allowed_sources(
    monkeypatch, tmp_path, config_value, expected_kwarg
) -> None:
    """make_lookup must thread cfg.aichemy_pricing.allowed_sources into
    PubChemCompoundResolver.from_files() preserving three distinct states:
    None (no filter), [] (filter to nothing), and a populated list (filter
    to those sources). Truthiness collapsing [] -> None is the OOM bug Task 4
    exists to prevent."""
    from aichemy.config import (
        AichemyPricingConfig,
        PreprocessingConfig,
        PricesConfig,
    )
    from aichemy.preprocessing.augment import prices as prices_mod

    # Stage all three required PubChem inputs so the missing-input fallback
    # doesn't short-circuit.
    compound_dir = tmp_path / "compound"
    compound_dir.mkdir()
    (compound_dir / "stub.sdf").write_text("$$$$\n")
    substance_dir = tmp_path / "substance"
    substance_dir.mkdir()
    (substance_dir / "stub.sdf").write_text("$$$$\n")
    sid_map_path = tmp_path / "sid_map.tsv"
    sid_map_path.write_text("")
    cache_path = tmp_path / "c.sqlite"
    index_cache = tmp_path / "index.parquet"  # does not exist yet -> triggers from_files

    captured: dict[str, object] = {}

    def fake_from_files(
        compound_sdf_paths,
        substance_sdf_paths,
        sid_map_path,
        allowed_sources=None,
        index_cache=None,
    ):
        captured["compound_sdf_paths"] = list(compound_sdf_paths)
        captured["substance_sdf_paths"] = list(substance_sdf_paths)
        captured["sid_map_path"] = sid_map_path
        captured["allowed_sources"] = allowed_sources
        captured["index_cache"] = index_cache
        from aichemy_pricing.resolvers.pubchem_compound import PubChemCompoundResolver

        return PubChemCompoundResolver()

    monkeypatch.setattr(
        "aichemy_pricing.resolvers.pubchem_compound.PubChemCompoundResolver.from_files",
        fake_from_files,
    )

    cfg = PreprocessingConfig(
        prices=PricesConfig(
            backend="aichemy_pricing",
            aichemy_pricing=AichemyPricingConfig(
                compound_dir=compound_dir,
                substance_dir=substance_dir,
                sid_map_path=sid_map_path,
                index_cache=index_cache,
                cache_path=cache_path,
                allowed_sources=config_value,
                max_workers=4,
            ),
        ),
    )

    prices_mod.make_lookup(cfg)
    if expected_kwarg is None:
        assert captured["allowed_sources"] is None
    else:
        assert captured["allowed_sources"] == expected_kwarg


def test_make_lookup_aichemy_pricing_uses_index_cache_when_present(monkeypatch, tmp_path) -> None:
    """If `index_cache` parquet exists, make_lookup must `from_cache` it and
    skip the 30-60 min build step entirely."""
    from aichemy.config import AichemyPricingConfig, PreprocessingConfig, PricesConfig
    from aichemy.preprocessing.augment import prices as prices_mod
    from aichemy_pricing.resolvers.pubchem_compound import PubChemCompoundResolver

    # Materialize a real cache by persisting an empty index.
    cache_path = tmp_path / "c.sqlite"
    index_cache = tmp_path / "index.parquet"
    PubChemCompoundResolver()._persist(index_cache)
    assert index_cache.exists()

    called = {"from_cache": False, "from_files": False}

    def fake_from_cache(parquet_path):
        called["from_cache"] = True
        return PubChemCompoundResolver()

    def fake_from_files(*args, **kwargs):
        called["from_files"] = True
        return PubChemCompoundResolver()

    monkeypatch.setattr(
        "aichemy_pricing.resolvers.pubchem_compound.PubChemCompoundResolver.from_cache",
        fake_from_cache,
    )
    monkeypatch.setattr(
        "aichemy_pricing.resolvers.pubchem_compound.PubChemCompoundResolver.from_files",
        fake_from_files,
    )

    cfg = PreprocessingConfig(
        prices=PricesConfig(
            backend="aichemy_pricing",
            aichemy_pricing=AichemyPricingConfig(
                compound_dir=tmp_path,  # contents irrelevant — cache hit short-circuits
                substance_dir=tmp_path,
                sid_map_path=tmp_path / "no.tsv",
                index_cache=index_cache,
                cache_path=cache_path,
            ),
        ),
    )
    prices_mod.make_lookup(cfg)
    assert called["from_cache"] is True
    assert called["from_files"] is False


def test_augment_prices_serial_default_unchanged() -> None:
    """max_workers=1 must produce the same DataFrame as the prior serial
    implementation (back-compat for existing DVC runs)."""
    import polars as pl

    from aichemy.preprocessing.augment.prices import StubPriceLookup, augment_prices

    df = pl.DataFrame({"canonical_smiles": ["CCO", "CCO", "CCC", "O"]})
    lookup = StubPriceLookup({"CCO": 0.003, "CCC": None, "O": 0.0001})
    out = augment_prices(df, lookup, max_workers=1)
    assert out.get_column("price_per_gram").to_list() == [0.003, 0.003, None, 0.0001]


def test_augment_prices_parallel_dispatch_matches_serial() -> None:
    """With max_workers > 1, the result DataFrame must be identical to the
    serial result (deterministic regardless of thread scheduling)."""
    import polars as pl

    from aichemy.preprocessing.augment.prices import StubPriceLookup, augment_prices

    smiles_unique = [f"C{i}" for i in range(50)]  # 50 unique
    df = pl.DataFrame({"canonical_smiles": smiles_unique * 3})  # 150 rows, dedup → 50
    prices = {s: float(i) for i, s in enumerate(smiles_unique)}
    lookup = StubPriceLookup(prices)

    serial = augment_prices(df, lookup, max_workers=1)
    parallel = augment_prices(df, lookup, max_workers=10)
    assert serial.equals(parallel)


def test_augment_prices_parallel_actually_runs_concurrently() -> None:
    """Sanity-check that max_workers>1 actually parallelizes: a lookup with a
    100ms sleep should complete in <1s for 20 unique SMILES at max_workers=10
    (vs ~2s serial). Loose assertion to avoid flake."""
    import time

    import polars as pl

    from aichemy.preprocessing.augment.prices import augment_prices

    class _SlowLookup:
        def lookup(self, smiles: str) -> float | None:
            time.sleep(0.1)
            return 1.0

    df = pl.DataFrame({"canonical_smiles": [f"C{i}" for i in range(20)]})
    t0 = time.monotonic()
    augment_prices(df, _SlowLookup(), max_workers=10)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0, f"parallel dispatch too slow: {elapsed:.2f}s (expected <1s)"

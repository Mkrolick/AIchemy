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

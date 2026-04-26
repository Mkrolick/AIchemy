"""Unit tests for CachedPriceLookup (SQLite-backed)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aichemy_pricing.chain import CachedPriceLookup
from aichemy_pricing.types import PriceQuote, VendorRef


class _HitOnce:
    name = "hit-once"

    def __init__(self) -> None:
        self.calls = 0

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        self.calls += 1
        return PriceQuote(
            vendor=ref.vendor,
            sku=ref.sku,
            price=1.0,
            currency="USD",
            pack_size_g=1.0,
            fetched_at=datetime.now(UTC),
        )


class _AlwaysMiss:
    name = "miss"

    def __init__(self) -> None:
        self.calls = 0

    def lookup(self, ref: VendorRef) -> PriceQuote | None:
        self.calls += 1
        return None


def test_cache_only_calls_inner_once_per_ref(tmp_path) -> None:
    inner = _HitOnce()
    cache = CachedPriceLookup(inner, db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="x", sku="y")
    cache.lookup(ref)
    cache.lookup(ref)
    cache.lookup(ref)
    assert inner.calls == 1


def test_cache_caches_misses(tmp_path) -> None:
    inner = _AlwaysMiss()
    cache = CachedPriceLookup(inner, db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="x", sku="y")
    assert cache.lookup(ref) is None
    assert cache.lookup(ref) is None
    assert inner.calls == 1


def test_cache_ttl_expiry_re_queries_inner(tmp_path) -> None:
    inner = _HitOnce()
    cache = CachedPriceLookup(inner, db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="x", sku="y")
    cache.lookup(ref)
    # Manually rewind the cached fetched_at by 60 days
    past = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    cache._conn().execute("UPDATE quote_cache SET fetched_at = ?", (past,))
    cache.lookup(ref)
    assert inner.calls == 2


def test_cache_round_trips_pricequote_fields(tmp_path) -> None:
    inner = _HitOnce()
    cache = CachedPriceLookup(inner, db_path=tmp_path / "c.sqlite", ttl_days=30)
    ref = VendorRef(vendor="vx", sku="sx")
    a = cache.lookup(ref)
    b = cache.lookup(ref)  # served from cache
    assert a is not None and b is not None
    assert (b.vendor, b.sku, b.price, b.currency) == (a.vendor, a.sku, a.price, a.currency)


def test_cached_lookup_is_thread_safe(tmp_path) -> None:
    """Many threads hitting the same CachedPriceLookup must not raise
    sqlite3.ProgrammingError ('SQLite objects created in a thread can only be
    used in that same thread.'). Regression guard for production
    parallelization in augment_prices."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from aichemy_pricing.chain import CachedPriceLookup
    from aichemy_pricing.types import PriceQuote, VendorRef

    class _StubInner:
        name = "stub"

        def lookup(self, ref: VendorRef) -> PriceQuote | None:
            return PriceQuote(
                vendor=ref.vendor,
                sku=ref.sku,
                price=1.0,
                currency="USD",
                pack_size_g=1.0,
                fetched_at=datetime.now(UTC),
            )

    cache = CachedPriceLookup(_StubInner(), db_path=tmp_path / "c.sqlite", ttl_days=30)

    refs = [VendorRef(vendor="enamine", sku=f"EN-{i}") for i in range(100)]
    errors: list[BaseException] = []
    barrier = threading.Barrier(20)

    def _run(ref: VendorRef) -> None:
        try:
            barrier.wait()
            assert cache.lookup(ref) is not None
        except BaseException as exc:
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(_run, refs))

    assert errors == [], f"thread-safety violations: {errors[:3]}"

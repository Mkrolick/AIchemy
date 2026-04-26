from pathlib import Path

from aichemy.preprocessing.patents.cache import (
    LLMCacheEntry,
    append_cache,
    load_cache,
)


def test_load_cache_missing_file_returns_empty(tmp_path: Path):
    cache_path = tmp_path / "cache.jsonl"
    assert load_cache(cache_path) == {}


def test_append_then_load_roundtrip(tmp_path: Path):
    cache_path = tmp_path / "cache.jsonl"
    e = LLMCacheEntry(
        patent_number="123",
        process_covered=True,
        composition_covered=False,
        confidence=0.9,
        rationale="claim 1 covers a method",
        model="claude-haiku-4-5",
        ts="2026-04-25T00:00:00Z",
    )
    append_cache(cache_path, e)
    loaded = load_cache(cache_path)
    assert "123" in loaded
    assert loaded["123"].process_covered is True


def test_later_entry_wins_for_duplicate_keys(tmp_path: Path):
    cache_path = tmp_path / "cache.jsonl"
    e1 = LLMCacheEntry(
        patent_number="X",
        process_covered=False,
        composition_covered=False,
        confidence=0.5,
        rationale="r1",
        model="m1",
        ts="2026-01-01T00:00:00Z",
    )
    e2 = LLMCacheEntry(
        patent_number="X",
        process_covered=True,
        composition_covered=True,
        confidence=0.9,
        rationale="r2",
        model="m1",
        ts="2026-04-01T00:00:00Z",
    )
    append_cache(cache_path, e1)
    append_cache(cache_path, e2)
    loaded = load_cache(cache_path)
    assert loaded["X"].process_covered is True
    assert loaded["X"].rationale == "r2"

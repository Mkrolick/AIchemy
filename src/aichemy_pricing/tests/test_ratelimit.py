"""Unit tests for TokenBucket. Uses small rate to keep test wall-time ≤2s."""

from __future__ import annotations

import time

import pytest

from aichemy_pricing.ratelimit import TokenBucket


def test_token_bucket_initial_tokens_do_not_block() -> None:
    bucket = TokenBucket(rate_per_sec=2.0, capacity=2)
    t0 = time.monotonic()
    bucket.acquire()
    bucket.acquire()
    elapsed = time.monotonic() - t0
    assert elapsed < 0.1


def test_token_bucket_blocks_after_exhaustion() -> None:
    bucket = TokenBucket(rate_per_sec=4.0, capacity=2)  # 0.25s per token after exhaustion
    t0 = time.monotonic()
    bucket.acquire()
    bucket.acquire()  # consume capacity
    bucket.acquire()  # third should block ~0.25s
    elapsed = time.monotonic() - t0
    assert 0.2 < elapsed < 1.0


def test_token_bucket_rejects_invalid_acquire() -> None:
    bucket = TokenBucket(rate_per_sec=1.0, capacity=1)
    with pytest.raises(ValueError):
        bucket.acquire(0)
    with pytest.raises(ValueError):
        bucket.acquire(-1)

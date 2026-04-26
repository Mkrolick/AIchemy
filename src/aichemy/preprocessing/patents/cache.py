"""JSONL append-only cache for LLM patent classifications.

One entry per LLM call. Cache key is `patent_number`. PatentsView is
canonical (abstract/claims for a given patent_number are stable), so the
cache hit on `patent_number` alone is correct.

Append-only design means the file is human-readable, easy to inspect, and
each invocation extends the file rather than rewriting it. On read, later
entries with the same `patent_number` win.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class LLMCacheEntry:
    patent_number: str
    process_covered: bool
    composition_covered: bool
    confidence: float
    rationale: str
    model: str
    ts: str


def load_cache(path: Path) -> dict[str, LLMCacheEntry]:
    """Read cache; later entries with the same patent_number win."""
    if not path.exists():
        return {}
    out: dict[str, LLMCacheEntry] = {}
    with open(path) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            data = json.loads(line)
            out[data["patent_number"]] = LLMCacheEntry(**data)
    return out


def append_cache(path: Path, entry: LLMCacheEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(asdict(entry)) + "\n")

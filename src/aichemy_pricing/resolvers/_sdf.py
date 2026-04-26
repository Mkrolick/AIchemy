"""Streaming SDF parser. Memory-bounded: yields one dict-of-tags per `$$$$`.

Handles both plain-text `.sdf` and gzipped `.sdf.gz` files transparently —
the PubChem FTP dump (CLAIM-04) ships 982 `.sdf.gz` files, and sub-plan E's
AIchemy backend integration globs `*.sdf*` so both extensions reach this
parser. Without gzip detection, opening deflate bytes as `errors="replace"`
text silently yields zero records (no UnicodeDecodeError, no log line) and
every downstream price lookup returns None for the wrong reason.
"""

from __future__ import annotations

import gzip
from collections.abc import Iterator
from pathlib import Path
from typing import IO, cast


def _open_text(path: Path) -> IO[str]:
    if path.suffix == ".gz":
        return cast(IO[str], gzip.open(path, "rt", errors="replace"))
    return path.open("rt", errors="replace")


def iter_sdf_records(path: Path) -> Iterator[dict[str, list[str]]]:
    """Yield {tag_name: [line, ...]} for each SDF record in `path`.

    Records are delimited by lines containing only `$$$$`. Tag values are the
    lines following `> <TAG>` up to the next blank line. Records without a
    trailing `$$$$` are not yielded (defensive behavior for truncated dumps).
    `.sdf.gz` files are opened transparently via gzip.
    """
    record: dict[str, list[str]] = {}
    current_tag: str | None = None
    with _open_text(path) as f:
        for raw in f:
            line = raw.rstrip("\n")
            if line == "$$$$":
                if record:
                    yield record
                record = {}
                current_tag = None
            elif line.startswith("> <") and line.endswith(">"):
                current_tag = line[3:-1]
                record.setdefault(current_tag, [])
            elif current_tag is not None and line == "":
                current_tag = None
            elif current_tag is not None:
                record[current_tag].append(line)

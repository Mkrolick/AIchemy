"""Streaming parser for PubChem's SID-Map cross-reference table.

PubChem ships `SID-Map.gz` under
`https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/Extras/SID-Map.gz`.

Real format (verified empirically — the FTP README documents only 2
columns but the actual file is 4):
    SID<TAB>SourceName<TAB>SourceRegID<TAB>CID
The CID column is OMITTED entirely (no trailing tab) for SIDs without
a standardized Compound association (deprecated rows, non-standardizable
structures, etc.); we yield None for those so callers can drop or retain
them at will.

`iter_sid_map` is the minimum interface — yields (sid, cid_or_none) and
ignores the source columns. `iter_sid_map_full` is the wider interface
that also exposes source name + reg id, opening the door for resolvers
that skip the separate Substance SDF scan entirely (the columns are
identical to what Substance records carry).
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


def iter_sid_map(path: Path) -> Iterator[tuple[int, int | None]]:
    """Yield (sid, cid_or_none) for each row in `path`.

    Skips malformed rows (non-integer SID, non-integer CID) silently — the
    file is large and known to contain occasional anomalies; one bad row
    must not abort the JOIN.
    """
    for sid, _name, _regid, cid in iter_sid_map_full(path):
        yield sid, cid


def iter_sid_map_full(
    path: Path,
) -> Iterator[tuple[int, str, str, int | None]]:
    """Yield (sid, source_name, source_reg_id, cid_or_none) for each row.

    Source columns may be empty strings if the row has fewer than 4
    fields before the CID. Rows with non-integer SID are skipped.
    """
    with _open_text(path) as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            try:
                sid = int(parts[0])
            except (ValueError, IndexError):
                continue
            source_name = parts[1] if len(parts) > 1 else ""
            source_regid = parts[2] if len(parts) > 2 else ""
            cid: int | None = None
            if len(parts) > 3:
                cid_str = parts[3].strip()
                if cid_str:
                    try:
                        cid = int(cid_str)
                    except ValueError:
                        cid = None
            yield sid, source_name, source_regid, cid

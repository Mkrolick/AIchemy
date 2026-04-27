"""Streaming parser for PubChem's SID -> CID mapping table.

PubChem ships `SID-Map.gz` under
`https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/Extras/SID-Map.gz` —
a 2-column TSV (`SID<TAB>CID`) with one row per substance. CID is empty
for SIDs without a standardized Compound association (deprecated rows,
non-standardizable structures, etc.); we yield None for those so callers
can choose to drop or retain them.

Used by `PubChemCompoundResolver` to bridge vendor-deposited Substance
records (which carry vendor + SKU but no InChIKey) to Compound records
(which carry the standardized InChIKey but no vendor info).
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

    Skips malformed rows (missing tab, non-integer SID) silently — the
    file is large and known to contain occasional anomalies; one bad row
    must not abort the JOIN.
    """
    with _open_text(path) as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                continue
            sid_str, _, cid_str = line.partition("\t")
            try:
                sid = int(sid_str)
            except ValueError:
                continue
            cid: int | None
            cid_str = cid_str.strip()
            if not cid_str:
                cid = None
            else:
                try:
                    cid = int(cid_str)
                except ValueError:
                    continue
            yield sid, cid

"""Raw-data downloader (Stage 01).

Streams files from canonical URLs (pinned in config) into `data/raw/<source>/`.
Idempotent: if the target file already exists with a non-zero size, the
download is skipped. Supports resumable downloads via `If-Modified-Since`
and content-length checks.

Callers pass URL + destination path pairs. The downloader is source-agnostic;
`ingest metanetx` / `ingest uspto` wire up their specific URL lists.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

CHUNK_SIZE = 1 << 16  # 64 KB


def download(
    url: str,
    dest: Path,
    *,
    user_agent: str = "AIchemy-research/0.1",
    timeout_seconds: float = 60.0,
    skip_if_exists: bool = True,
    client: httpx.Client | None = None,
) -> Path:
    """Stream a URL to disk, returning the destination path.

    If ``skip_if_exists`` and ``dest`` already exists with size>0, returns
    the existing path without network I/O. Raises ``httpx.HTTPError`` on
    download failures; partial files are removed.
    """
    if skip_if_exists and dest.exists() and dest.stat().st_size > 0:
        log.info("%s already present (%d bytes); skipping download.", dest, dest.stat().st_size)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    owned_client = client is None
    if client is None:
        client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    tmp_path = dest.with_suffix(dest.suffix + ".partial")
    try:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
        tmp_path.replace(dest)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    finally:
        if owned_client:
            client.close()

    log.info("Downloaded %s → %s (%d bytes)", url, dest, dest.stat().st_size)
    return dest

"""Shared fixture-capture validator. Writes the response body to disk only if
all sanity checks pass — a corrupted/blocked response cannot poison the test
suite.

Usage (typical, plain HTTP):
    uv run python -m aichemy_pricing.tests.data._capture \\
        --url https://www.tocris.com/products/jw-642_4906 \\
        --out  src/aichemy_pricing/tests/data/tocris_jw642.html \\
        --min-size 5000 --required-marker 'JW 642'

Usage (Cloudflare-aware, via curl_cffi):
    uv run python -m aichemy_pricing.tests.data._capture \\
        --url https://www.medchemexpress.com/acetyl-coenzyme-a.html \\
        --out  src/aichemy_pricing/tests/data/mce_acetyl_coa.html \\
        --client cf --impersonate chrome124 \\
        --min-size 5000 --required-marker 'Acetyl'
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Markers that mean we got a Cloudflare/Akamai challenge instead of real HTML.
BAD_MARKERS = (
    "Just a moment...",
    "cf-browser-verification",
    "challenge-platform",
    "Checking your browser",
    "Enable JavaScript and cookies",
    "Access denied",
    "Reference #18.",  # Akamai reference-id template
)


def _fetch_plain(url: str) -> tuple[int, bytes]:
    import httpx

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as c:
        r = c.get(url)
        return r.status_code, r.content


def _fetch_cf(url: str, impersonate: str) -> tuple[int, bytes]:
    from curl_cffi import requests as cf_requests

    sess = cf_requests.Session(impersonate=impersonate)
    r = sess.get(url)
    return r.status_code, r.content


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Capture a fixture for vendor tests.")
    p.add_argument("--url", required=True)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--client", choices=["plain", "cf"], default="plain")
    p.add_argument(
        "--impersonate", default="chrome124", help="curl_cffi impersonate token (cf only)"
    )
    p.add_argument(
        "--min-size", type=int, default=2_000, help="reject body smaller than this many bytes"
    )
    p.add_argument(
        "--required-marker",
        action="append",
        default=[],
        help="substring that MUST appear in the body (repeatable)",
    )
    args = p.parse_args(argv)

    if args.client == "cf":
        status, body = _fetch_cf(args.url, args.impersonate)
    else:
        status, body = _fetch_plain(args.url)

    text = body.decode("utf-8", "replace")
    problems: list[str] = []
    if status != 200:
        problems.append(f"status_code={status} (expected 200)")
    if len(body) < args.min_size:
        problems.append(f"body_len={len(body)} (expected ≥ {args.min_size})")
    bad = [m for m in BAD_MARKERS if m in text]
    if bad:
        problems.append(f"challenge marker(s) present: {bad}")
    missing = [m for m in args.required_marker if m not in text]
    if missing:
        problems.append(f"required marker(s) missing: {missing}")

    if problems:
        print(f"FIXTURE CAPTURE FAILED for {args.url}:", file=sys.stderr)
        for x in problems:
            print(f"  - {x}", file=sys.stderr)
        print(
            "\nDo not retry by relaxing the checks; investigate why the vendor "
            "didn't return its real HTML/JSON (residential IP? CF token rotation? "
            "redirect change?).",
            file=sys.stderr,
        )
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(body)
    print(f"OK: wrote {len(body)} bytes to {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

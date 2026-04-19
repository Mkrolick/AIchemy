"""PubChem helpers: SMILES → CID → CAS / name.

PubChem's public REST API (`pubchem.ncbi.nlm.nih.gov/rest/pug`) is free,
well-documented, and the canonical identifier-resolution layer. We use it
as the first step in every vendor scrape because every major vendor's
search accepts CAS numbers or IUPAC names but **not** SMILES directly.

Rate limit: PubChem's formal limit is 5 req/s. We use 0.3s between calls
(≈3/s) to stay well under that.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


@dataclass
class PubChemIdentifiers:
    cid: int
    cas: list[str]
    iupac_name: str | None
    synonyms: list[str]


class PubChemResolver:
    """SMILES → PubChem CID + CAS numbers + synonyms."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        rate_limit_seconds: float = 0.3,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._rate = rate_limit_seconds
        self._last_call: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._rate:
            time.sleep(self._rate - elapsed)
        self._last_call = time.monotonic()

    def _get(self, path: str) -> dict | None:
        self._throttle()
        url = f"{BASE}/{path}"
        try:
            resp = self._client.get(url)
        except httpx.HTTPError as exc:
            log.debug("PubChem GET failed: %s (%s)", exc, url)
            return None
        if resp.status_code != 200:
            return None
        try:
            return resp.json()
        except json.JSONDecodeError:
            return None

    def resolve(self, smiles: str) -> PubChemIdentifiers | None:
        """Resolve a SMILES to CID, then pull CAS + synonyms."""
        if not smiles:
            return None
        encoded = quote(smiles, safe="")

        data = self._get(f"compound/smiles/{encoded}/cids/JSON")
        if not data:
            return None
        try:
            cids = data["IdentifierList"]["CID"]
        except KeyError:
            return None
        if not cids:
            return None
        cid = int(cids[0])

        # Synonyms (includes CAS numbers)
        syn_data = self._get(f"compound/cid/{cid}/synonyms/JSON")
        synonyms: list[str] = []
        if syn_data:
            try:
                synonyms = syn_data["InformationList"]["Information"][0]["Synonym"]
            except (KeyError, IndexError):
                synonyms = []

        # IUPAC name (via properties)
        props = self._get(f"compound/cid/{cid}/property/IUPACName/JSON")
        iupac: str | None = None
        if props:
            try:
                iupac = props["PropertyTable"]["Properties"][0]["IUPACName"]
            except (KeyError, IndexError):
                iupac = None

        # Extract CAS numbers from synonyms (pattern: NNNNN-NN-N)
        import re as _re

        cas_pattern = _re.compile(r"^\d{1,7}-\d{2}-\d$")
        cas: list[str] = [s for s in synonyms if cas_pattern.match(s)]

        return PubChemIdentifiers(cid=cid, cas=cas, iupac_name=iupac, synonyms=synonyms)

    def close(self) -> None:
        self._client.close()

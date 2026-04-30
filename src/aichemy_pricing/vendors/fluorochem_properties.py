"""Fluorochem product-page chemistry-metadata scraper.

Sibling to ``fluorochem.py`` (which fetches pricing from the Azure-blob JSON
endpoint). This module fetches the user-facing product page at
``https://fluorochem.co.uk/product/{SKU}/`` and extracts chemistry metadata
that is NOT in the pricing JSON.

Two extraction strategies, layered:

1. **JSON-LD ``additionalProperty`` block** (schema.org/Product). Stable,
   SEO-driven. Provides:
     CAS Number, Purity, IUPAC Name, Canonical Smiles, InChI, InChI Key,
     MDL Number, UNSPSC Code, SKU.

2. **HTML "product-info" table** (rendered alongside JSON-LD). Richer:
     Molecular Weight, LogP, H Bond Acceptors / Donors, Fsp3,
     UN Number, Packing Group, Hazard Class, Shipping Name —
     plus everything in (1) again, redundantly.

The two strategies are merged with HTML winning on conflicts (HTML is
more numerically precise for properties like MW; JSON-LD truncates to
the SEO description string). Anything either source produces lands in
``raw_property_map`` for forward-compat. The dataclass exposes the
well-known fields as typed attributes.

Motivation:
  - Purity feeds the MILP mass-balance (``$X/g`` at 98% purity means 980mg
    of active per gram, not 1g).
  - Molecular weight feeds the parallel "molar coefficients vs gram
    coefficients" fix in the solver mass-balance (the current dimensional
    bug). A reliable MW per molecule is exactly what that fix needs.
  - LogP / Fsp3 / H-bond counts are physicochemical descriptors useful
    for downstream filtering or model-based property prediction.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from aichemy_pricing.http import make_plain_client

log = logging.getLogger(__name__)

_PRODUCT_URL_TEMPLATE = "https://fluorochem.co.uk/product/{sku}/"

# JSON-LD blocks live in <script type="application/ld+json">…</script> in the
# document head. Fluorochem typically emits multiple (one per schema.org type
# they advertise — Product, Organization, BreadcrumbList, etc.); we want only
# the Product block, which is the one that carries `additionalProperty`.
_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

# HTML "product-info" table fields. Each field renders as:
#   <h3>LABEL</h3>...</div>
#   <div class="product-info__field-value ...">VALUE</div>
# This pattern catches MW / LogP / hazard fields that aren't in JSON-LD.
_HTML_FIELD_RE = re.compile(
    r"<h3>([^<]+)</h3>\s*</div>\s*"
    r'<div class="product-info__field-value[^"]*">\s*([^<]+?)\s*</div>',
    re.DOTALL,
)


@dataclass
class FluorochemProperties:
    """Chemistry metadata harvested from a Fluorochem product page.

    Every attribute is optional because (a) some product pages omit fields
    and (b) we want to capture *whatever* is present, not fail on a missing
    purity. The caller can then decide what to do when a field is None.

    Numeric fields (``molecular_weight``, ``logp``, ``fsp3``, ``hba``,
    ``hbd``) are typed; the corresponding raw text remains in
    ``raw_property_map`` for diagnostics.
    """

    sku: str
    name: str | None = None

    # Identity
    cas_number: str | None = None
    iupac_name: str | None = None
    canonical_smiles: str | None = None
    inchi: str | None = None
    inchi_key: str | None = None
    mdl_number: str | None = None

    # Quality
    purity_text: str | None = None  # raw "98%" / ">99%" / "tech grade"
    purity_fraction: float | None = None  # parsed: "98%" -> 0.98

    # Physicochemical (computed by Fluorochem from canonical structure)
    molecular_weight: float | None = None  # g/mol
    logp: float | None = None  # octanol-water partition (computed)
    hba: int | None = None  # H-bond acceptors
    hbd: int | None = None  # H-bond donors
    fsp3: float | None = None  # fraction of sp3 carbons

    # Hazard / shipping
    un_number: str | None = None
    packing_group: str | None = None
    hazard_class: str | None = None
    shipping_name: str | None = None

    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw_property_map: dict[str, str] = field(default_factory=dict)


def _to_float(s: str | None) -> float | None:
    """Lenient float parse: tolerates trailing units (\"179.24 g/mol\")
    and surrounding whitespace. Returns None on no-numeric-content."""
    if s is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _to_int(s: str | None) -> int | None:
    """Lenient int parse, mirrors ``_to_float``."""
    f = _to_float(s)
    if f is None:
        return None
    if float(int(f)) != f:  # don't silently truncate "1.5" to 1
        return None
    return int(f)


def _parse_purity_to_fraction(text: str | None) -> float | None:
    """Convert a raw purity string to a [0, 1] fraction.

    Handles:
        "98%"           -> 0.98
        ">99%"          -> 0.99    (drop comparator, lower bound)
        "≥97%"          -> 0.97
        "98.5%"         -> 0.985
        "tech grade"    -> None    (no numeric content)
        "98% (HPLC)"    -> 0.98    (extract first number)
        ""              -> None
    """
    if not text:
        return None
    # Capture optional leading sign so "-5%" doesn't accidentally match "5%".
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if not m:
        return None
    try:
        pct = float(m.group(1))
    except ValueError:
        return None
    if pct < 0 or pct > 100:
        return None
    return pct / 100.0


def parse_fluorochem_product_html(html: str, sku: str) -> FluorochemProperties:
    """Pure-function parser. Combines two extraction passes (JSON-LD and
    HTML "product-info" table) into a typed ``FluorochemProperties`` record.

    Fluorochem's JSON-LD shape (as of 2026-04):

        {
          "@type": "Product",
          "name": "...",
          "sku": "F765353",
          "additionalProperty": [
            {"@type": "PropertyValue", "name": "CAS Number", "value": "..."},
            {"@type": "PropertyValue", "name": "Purity", "value": "98%"},
            ...
          ]
        }

    HTML "product-info" table fields render as:

        <h3>Molecular Weight</h3>...</div>
        <div class="product-info__field-value ...">179.2380066</div>

    HTML wins on conflicts (it carries higher numeric precision; JSON-LD
    sometimes truncates values into the SEO description).

    Multiple JSON-LD scripts may be on the page; we pick the one whose
    ``@type`` is ``Product``. If no Product block AND no HTML fields are
    found, we still return a properties record with just the SKU set, so
    the caller can detect "page exists but is malformed" by checking
    ``.raw_property_map == {}``.
    """
    props = FluorochemProperties(sku=sku)

    # Pass 1: JSON-LD additionalProperty array
    for raw in _JSON_LD_RE.findall(html):
        body = raw.strip()
        if not body:
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            log.debug("[fluorochem properties] JSON-LD parse failed for %s", sku)
            continue
        data_list = data if isinstance(data, list) else [data]
        for entry in data_list:
            if not isinstance(entry, dict):
                continue
            if entry.get("@type") != "Product":
                continue
            props.name = entry.get("name") or props.name
            for ap in entry.get("additionalProperty", []) or []:
                if not isinstance(ap, dict):
                    continue
                key = ap.get("name")
                val = ap.get("value")
                if not key or val is None:
                    continue
                # Coerce non-string values (e.g. MDL Number returns as int)
                # to string for consistent dict typing.
                props.raw_property_map[str(key)] = str(val)

    # Pass 2: HTML product-info table (overrides JSON-LD on overlap because
    # HTML preserves full numeric precision).
    for raw_label, raw_value in _HTML_FIELD_RE.findall(html):
        label = raw_label.strip()
        value = re.sub(r"\s+", " ", raw_value).strip()
        if not label or not value:
            continue
        props.raw_property_map[label] = value

    # Lift well-known fields out of the raw map for typed access. Names match
    # Fluorochem's exact labels — case-sensitive.
    rm = props.raw_property_map

    # Identity
    props.cas_number = rm.get("CAS Number")
    props.iupac_name = rm.get("IUPAC Name") or rm.get("IUPAC")
    props.canonical_smiles = rm.get("Canonical Smiles")
    props.inchi = rm.get("InChI")
    props.inchi_key = rm.get("InChI Key")
    props.mdl_number = rm.get("MDL Number")

    # Quality
    props.purity_text = rm.get("Purity")
    props.purity_fraction = _parse_purity_to_fraction(props.purity_text)

    # Physicochemical
    props.molecular_weight = _to_float(rm.get("Molecular Weight"))
    props.logp = _to_float(rm.get("Logp") or rm.get("LogP"))
    props.hba = _to_int(rm.get("H Bond Acceptors"))
    props.hbd = _to_int(rm.get("H Bond Donors"))
    props.fsp3 = _to_float(rm.get("Fsp3"))

    # Hazard / shipping
    props.un_number = rm.get("Un Number") or rm.get("UN Number")
    props.packing_group = rm.get("Packing Group")
    props.hazard_class = rm.get("Hazard Class")
    props.shipping_name = rm.get("Shipping Name")

    return props


def fetch_fluorochem_properties(
    sku: str,
    *,
    client: httpx.Client | None = None,
) -> FluorochemProperties | None:
    """Fetch the public product page for ``sku`` and parse its JSON-LD.

    Returns:
        FluorochemProperties record, or None if the product page returns
        404 (i.e., SKU does not exist on the public site).

    Raises:
        httpx.HTTPStatusError on non-2xx, non-404 responses (5xx, etc.)
    """
    cli = client or make_plain_client()
    url = _PRODUCT_URL_TEMPLATE.format(sku=sku)
    resp = cli.get(url, follow_redirects=True)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return parse_fluorochem_product_html(resp.text, sku)


__all__ = [
    "FluorochemProperties",
    "fetch_fluorochem_properties",
    "parse_fluorochem_product_html",
]

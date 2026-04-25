"""USPTO ingestion (Stage 03).

Parses Lowe's tab-separated USPTO reaction-SMILES (`.rsmi`) dump into the
internal Reaction schema. The Lowe format is:

    ReactionSmiles\tPatentNumber\tParagraphNum\tYear\tTextMinedYield\tCalculatedYield

Reaction SMILES use `>` as the splitter: `reactants>agents>products` where
each side is a `.`-joined list of SMILES. Atom-mapping (`[Br:1]`) is
preserved in the raw column; the internal schema stores bare SMILES on
participants with coefficient=1.0 (SYN-RBL fixes real stoichiometry later).
"""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

log = logging.getLogger(__name__)


def _float_or_none(val: str | None) -> float | None:
    """Parse a yield string to a float in [0, 1], or None on failure.

    Raw USPTO values carry a '%' suffix on a 0–100 scale (e.g. '82.0%').
    Values already in [0, 1] are passed through unchanged. Values above 1.0
    are assumed to be on the 0–100 scale and divided by 100; the result is
    capped at 1.0 to absorb typo'd values like '100.5%'. Negative values and
    unparseable strings return None.
    """
    if val is None or val == "":
        return None
    s = val.strip().rstrip("%").strip()
    try:
        x = float(s)
    except (TypeError, ValueError):
        return None
    if x < 0:
        return None
    if x > 1.0:
        x = x / 100.0
    return min(x, 1.0)  # cap typo'd >100% values


def parse_reaction_smiles(rxn: str) -> tuple[list[str], list[str], list[str]]:
    """Split a reaction-SMILES string into (reactants, agents, products)."""
    parts = rxn.split(">")
    if len(parts) != 3:
        return [], [], []
    reactants, agents, products = parts

    def _split(side: str) -> list[str]:
        return [s for s in side.split(".") if s]

    return _split(reactants), _split(agents), _split(products)


def parse_rsmi_file(path: Path) -> pl.DataFrame:
    """Read a Lowe `.rsmi` file into a Polars DataFrame."""
    df = pl.read_csv(
        path,
        separator="\t",
        has_header=True,
        truncate_ragged_lines=True,
        quote_char=None,
        infer_schema_length=0,
    )
    rename_map = {
        "ReactionSmiles": "reaction_smiles",
        "PatentNumber": "patent_number",
        "ParagraphNum": "paragraph_num",
        "Year": "year",
        "TextMinedYield": "text_mined_yield",
        "CalculatedYield": "calculated_yield",
    }
    df = df.rename({k: v for k, v in rename_map.items() if k in df.columns})
    return df


def ingest_uspto(rsmi_path: Path) -> pl.DataFrame:
    """Ingest a USPTO `.rsmi` file and return a Reaction-schema DataFrame."""
    raw = parse_rsmi_file(rsmi_path)

    reactants_col: list[list[dict]] = []
    products_col: list[list[dict]] = []

    for rxn_smiles in raw["reaction_smiles"].to_list():
        if rxn_smiles is None:
            reactants_col.append([])
            products_col.append([])
            continue
        reactants, _agents, products = parse_reaction_smiles(rxn_smiles)
        reactants_col.append([{"mol_id": s, "coefficient": 1.0} for s in reactants])
        products_col.append([{"mol_id": s, "coefficient": 1.0} for s in products])

    text_mined = [_float_or_none(v) for v in raw.get_column("text_mined_yield").to_list()]
    calculated = [_float_or_none(v) for v in raw.get_column("calculated_yield").to_list()]
    yield_rate = [
        tm if tm is not None else calc for tm, calc in zip(text_mined, calculated, strict=True)
    ]

    patent = (
        raw["patent_number"].to_list() if "patent_number" in raw.columns else ["USPTO"] * raw.height
    )
    rxn_ids = [f"USPTO:{p}:{i}" for i, p in enumerate(patent)]

    return pl.DataFrame(
        {
            "rxn_id": rxn_ids,
            "reaction_smiles": raw["reaction_smiles"].to_list(),
            "reactants": reactants_col,
            "products": products_col,
            "type": ["chemical"] * raw.height,
            "yield_rate": yield_rate,
            "delta_g": [None] * raw.height,
            "balanced": [False] * raw.height,
            "source": ["uspto"] * raw.height,
            "ec_class": [None] * raw.height,
        },
        schema_overrides={
            "yield_rate": pl.Float64,
            "delta_g": pl.Float64,
            "balanced": pl.Boolean,
            "ec_class": pl.Utf8,
        },
    )

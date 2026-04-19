"""Solver-output benchmarks.

Provides:
- `known_profitable_molecules()`: a small curated list of real chemical
  intermediates with published market-scale profit margins. The solver
  should rediscover at least some of these as high-value products when
  given a rich-enough reaction network + realistic prices.
- `summarize_solution(solution, molecules)`: compact human-readable report
  (top-K activated reactions, top-K products by revenue, overall profit).
- `BenchmarkReport`: structured result of a benchmark run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import polars as pl

from aichemy.solver.model import Solution


@dataclass
class KnownMolecule:
    """A curated known-valuable chemical, used for recall benchmarks."""

    name: str
    canonical_smiles: str
    approx_price_per_gram_usd: float
    notes: str


# Small curated catalog — these are molecules with published market prices
# and real chemo-enzymatic synthesis routes. Use as recall benchmarks:
# the solver *should* tend to include these in its top sold products
# when run on a rich hypergraph with realistic pricing.
_KNOWN: list[KnownMolecule] = [
    KnownMolecule(
        name="vanillin",
        canonical_smiles="COc1cc(C=O)ccc1O",
        approx_price_per_gram_usd=0.15,
        notes="Food-grade flavor molecule, major biocatalytic market.",
    ),
    KnownMolecule(
        name="L-lysine",
        canonical_smiles="NCCCCC(N)C(=O)O",
        approx_price_per_gram_usd=0.003,
        notes="Bulk-commodity amino acid (~$3/kg), huge fermentation market.",
    ),
    KnownMolecule(
        name="citric acid",
        canonical_smiles="OC(=O)CC(O)(CC(=O)O)C(=O)O",
        approx_price_per_gram_usd=0.002,
        notes="Bulk organic acid via Aspergillus fermentation.",
    ),
    KnownMolecule(
        name="acetaminophen",
        canonical_smiles="CC(=O)Nc1ccc(O)cc1",
        approx_price_per_gram_usd=0.05,
        notes="OTC analgesic, high-volume pharma API.",
    ),
    KnownMolecule(
        name="shikimic acid",
        canonical_smiles="OC1CC(C(=O)O)=CC(O)C1O",
        approx_price_per_gram_usd=80.0,
        notes="Tamiflu precursor — peaked during pandemic supply crunch.",
    ),
    KnownMolecule(
        name="beta-carotene",
        canonical_smiles="CC(=CCCC(=CC=CC(=CC=CC=C(C)C=CC=C(C)C=CC1C(CCCC1(C)C)(C)C)C)C)C",
        approx_price_per_gram_usd=1.5,
        notes="Pro-vitamin A, bulk nutraceutical.",
    ),
]


def known_profitable_molecules() -> list[KnownMolecule]:
    """Return the curated catalog of known-valuable chemicals."""
    return list(_KNOWN)


@dataclass
class BenchmarkReport:
    status: str
    objective_value: float
    num_activated_reactions: int
    num_sold_molecules: int
    num_purchased_molecules: int
    top_sold: list[dict[str, Any]] = field(default_factory=list)
    top_purchased: list[dict[str, Any]] = field(default_factory=list)
    known_hits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "objective_value": self.objective_value,
            "num_activated_reactions": self.num_activated_reactions,
            "num_sold_molecules": self.num_sold_molecules,
            "num_purchased_molecules": self.num_purchased_molecules,
            "top_sold": self.top_sold,
            "top_purchased": self.top_purchased,
            "known_hits": self.known_hits,
        }


def summarize_solution(
    solution: Solution,
    molecules: pl.DataFrame | None = None,
    top_k: int = 10,
) -> BenchmarkReport:
    """Produce a `BenchmarkReport` from a solved MILP output.

    If `molecules` is passed (and has canonical_smiles), checks the sold-
    molecule list against the curated-known catalog and records matches
    in `known_hits`.
    """
    sold_sorted = sorted(
        solution.sold_molecules,
        key=lambda r: r.get("revenue", 0.0),
        reverse=True,
    )[:top_k]
    purchased_sorted = sorted(
        solution.purchased_molecules,
        key=lambda r: r.get("cost", 0.0),
        reverse=True,
    )[:top_k]

    known_hits: list[str] = []
    if molecules is not None and "canonical_smiles" in molecules.columns:
        sold_smiles: set[str] = set()
        mol_smiles_by_id = dict(
            zip(
                molecules["mol_id"].to_list(),
                molecules["canonical_smiles"].to_list(),
                strict=True,
            )
        )
        for sold in solution.sold_molecules:
            smi = mol_smiles_by_id.get(sold["mol_id"])
            if smi:
                sold_smiles.add(smi)
        for known in _KNOWN:
            if known.canonical_smiles in sold_smiles:
                known_hits.append(known.name)

    return BenchmarkReport(
        status=solution.status,
        objective_value=solution.objective_value,
        num_activated_reactions=len(solution.activated_reactions),
        num_sold_molecules=len(solution.sold_molecules),
        num_purchased_molecules=len(solution.purchased_molecules),
        top_sold=sold_sorted,
        top_purchased=purchased_sorted,
        known_hits=known_hits,
    )

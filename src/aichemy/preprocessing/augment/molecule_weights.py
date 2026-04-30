"""Per-molecule average molecular weight column for the processed table.

Adds a ``mol_weight`` (g/mol) column derived from each molecule's
``canonical_smiles`` via RDKit's ``Descriptors.MolWt`` (which returns
the isotope-abundance-weighted average MW — the right notion for a
per-gram pricing model that buys/sells natural-isotope material).

Why this lives at post-export rather than in the upstream normalize/
dedup chain: MW is purely a function of the molecule's structure, so
it has no logical dep on prices, patents, yields, or any other
augmentation. Computing it after ``export`` (a) keeps the ~20-min
RDKit pass off the critical path of the upstream pipeline, and
(b) means a re-derivation never invalidates patent fetches, LLM
classifications, or the pricing index.

The MW column is consumed by the MILP solver under
``SolverConfig.mass_basis=True`` (CLI ``--mass-basis``) to multiply
stoichiometric coefficients by participant MW so the mass-balance
constraint is dimensionally consistent in grams. See
``src/aichemy/solver/model.py`` for the consumer.

Failure mode: a SMILES that ``Chem.MolFromSmiles`` cannot parse
(class-metabolite wildcards that escaped resolve_class, malformed
fragments, etc.) yields a null ``mol_weight``. The solver drops the
whole reaction when any participant has a null MW; downstream
analysis can audit dropped-reaction count from the solver log.
"""

from __future__ import annotations

import polars as pl
from rdkit.Chem import Descriptors

from aichemy.preprocessing.chem.smiles import parse


def augment_with_mw(df: pl.DataFrame) -> pl.DataFrame:
    """Return ``df`` with a ``mol_weight`` (Float64, g/mol) column added.

    Reads ``canonical_smiles``; for each row, runs RDKit's
    ``Descriptors.MolWt`` on the parsed Mol. SMILES that fail to parse
    yield ``None`` (null in the resulting column). Row order is preserved.

    The input ``df`` must have a ``canonical_smiles`` column. All other
    columns are passed through unchanged.
    """
    if "canonical_smiles" not in df.columns:
        raise ValueError("augment_with_mw: input must have a 'canonical_smiles' column")

    weights: list[float | None] = []
    for smi in df["canonical_smiles"].to_list():
        mol = parse(smi)
        if mol is None:
            weights.append(None)
        else:
            weights.append(float(Descriptors.MolWt(mol)))
    return df.with_columns(pl.Series("mol_weight", weights, dtype=pl.Float64))

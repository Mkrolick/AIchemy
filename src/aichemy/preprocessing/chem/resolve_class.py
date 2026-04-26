"""Class-metabolite resolver.

MetaNetX uses ``[*]`` wildcard atoms in SMILES to represent class-level
metabolites (e.g. "any acyl-CoA"). RDKit accepts these as wildcard atoms
in SMILES, but ``MolToInchi`` rejects them — InChI requires every atom to
be a real element. As a result, those rows carry through the pipeline with
``inchi_key = None`` and never collapse during dedup.

This module resolves wildcard SMILES to a real InChIKey-bearing form via a
layered strategy. Public entrypoints are layered, lowest-cost first:

- ``substitute_wildcards`` (Layer A): deterministic R-group fallback. Replaces
  every ``[*]`` with a methyl carbon, re-canonicalizes, and returns the
  result. Always available; output is chemically arbitrary but produces a
  stable InChIKey usable for grouping.
- ``resolve_via_chebi`` (Layer B): walks the ChEBI ``is_a`` ontology to a
  concrete leaf (added in a later iteration).
- ``resolve_via_ec`` (Layer C): infers an exemplar from sibling reactions
  in the same EC class (added in a later iteration).
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import polars as pl
from rdkit import Chem

log = logging.getLogger(__name__)


_OBO_SMILES_RE = re.compile(r'property_value:\s+\S+/smiles\s+"([^"]+)"')
_OBO_ISA_RE = re.compile(r"is_a:\s+(CHEBI:\d+)")
_OBO_ID_RE = re.compile(r"id:\s+(CHEBI:\d+)")


def parse_chebi_obo(path: Path) -> dict[str, Any]:
    """Parse a ChEBI OBO file into id→SMILES and parent→children indexes.

    Returns a dict::

        {
            "id_to_smiles": {chebi_id: smiles_or_None},
            "children":     {parent_id: [child_id, ...]},
        }

    Only the fields needed for downstream resolution are extracted (id,
    is_a, smiles). The OBO file is large (~200 MB) but a single pass is
    enough; parse output should be cached as JSON for repeat runs.
    """
    id_to_smiles: dict[str, str | None] = {}
    children: dict[str, list[str]] = defaultdict(list)

    current_id: str | None = None
    current_smiles: str | None = None
    current_parents: list[str] = []
    in_term = False

    def _flush() -> None:
        nonlocal current_id, current_smiles, current_parents
        if current_id is not None:
            id_to_smiles[current_id] = current_smiles
            for parent in current_parents:
                children[parent].append(current_id)
        current_id = None
        current_smiles = None
        current_parents = []

    with path.open() as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("[Term]"):
                _flush()
                in_term = True
                continue
            if line.startswith("[") and line.endswith("]"):
                # Other stanza type (e.g. [Typedef]) — flush and stop tracking
                _flush()
                in_term = False
                continue
            if not in_term or not line:
                continue
            m = _OBO_ID_RE.match(line)
            if m:
                current_id = m.group(1)
                continue
            m = _OBO_ISA_RE.match(line)
            if m:
                current_parents.append(m.group(1))
                continue
            m = _OBO_SMILES_RE.match(line)
            if m:
                current_smiles = m.group(1)
                continue
        _flush()

    return {"id_to_smiles": id_to_smiles, "children": dict(children)}


def resolve_via_chebi(chebi_id: str, parsed: dict[str, Any]) -> str | None:
    """Resolve a ChEBI class ID to a concrete-leaf SMILES via is_a descent.

    If ``chebi_id`` itself has a non-wildcard SMILES, return it directly.
    Otherwise BFS through descendants and return the first concrete SMILES
    (no ``[*]``). Returns None if the ID is unknown or no concrete leaf
    exists in the subtree.
    """
    id_to_smiles: dict[str, str | None] = parsed.get("id_to_smiles", {})
    children: dict[str, list[str]] = parsed.get("children", {})

    if chebi_id not in id_to_smiles and chebi_id not in children:
        return None

    def _is_concrete(smi: str | None) -> bool:
        return bool(smi) and "[*]" not in (smi or "")

    own = id_to_smiles.get(chebi_id)
    if _is_concrete(own):
        return own

    seen: set[str] = {chebi_id}
    queue: deque[str] = deque(children.get(chebi_id, []))
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        smi = id_to_smiles.get(node)
        if _is_concrete(smi):
            return smi
        queue.extend(children.get(node, []))
    return None


def drop_unreferenced_empty_molecules(
    molecules: pl.DataFrame,
    reactions: pl.DataFrame,
) -> pl.DataFrame:
    """Drop molecules whose canonical_smiles is empty/null AND that no reaction references.

    MetaNetX's chem_prop catalog includes ~35K cross-reference entries with no
    structural data (empty SMILES, empty InChIKey) that don't appear in any
    curated reaction. They're pure dead weight downstream — every augmentation
    stage produces nulls for them, and dedup can't collapse them. Drop them
    here.

    Rows with empty SMILES that ARE referenced by a reaction must be kept —
    dropping them would lose the reaction. Those need a richer SMILES-recovery
    strategy (cross-DB lookup) which lives in a separate resolver layer.
    """
    if molecules.height == 0:
        return molecules
    empty_mask = molecules["canonical_smiles"].is_null() | (molecules["canonical_smiles"] == "")
    if not empty_mask.any():
        return molecules

    referenced: set[str] = set()
    if reactions.height > 0:
        for col in ("reactants", "products"):
            if col not in reactions.columns:
                continue
            for parts in reactions[col].to_list():
                for p in parts or []:
                    mid = p.get("mol_id") if isinstance(p, dict) else None
                    if mid:
                        referenced.add(mid)

    keep_mask = ~empty_mask | molecules["mol_id"].is_in(list(referenced))
    return molecules.filter(keep_mask)


def substitute_wildcards(smiles: str) -> str | None:
    """Replace ``[*]`` wildcards with methyl carbons; return canonical SMILES.

    Returns None if:
    - the SMILES is empty or unparseable
    - the SMILES does not contain ``[*]`` (no work to do — caller should
      treat the original SMILES as already concrete)

    The substituted SMILES is guaranteed to be parseable by RDKit. It is
    NOT guaranteed to be a chemically meaningful exemplar of the class —
    this is a deterministic fallback used when richer resolvers (ChEBI
    ontology, EC-context) cannot find a real exemplar.
    """
    if not smiles or "[*]" not in smiles:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    # Replace each wildcard atom (atomic number 0) with a carbon.
    rw = Chem.RWMol(mol)
    for atom in rw.GetAtoms():  # type: ignore[no-untyped-call]
        if atom.GetAtomicNum() == 0:
            atom.SetAtomicNum(6)
            atom.SetNoImplicit(False)
            atom.SetNumExplicitHs(0)
    try:
        Chem.SanitizeMol(rw)
    except (Chem.AtomValenceException, Chem.KekulizeException):
        return None
    return Chem.MolToSmiles(rw, canonical=True)


def _compute_inchi_key(smiles: str) -> str | None:
    """Return the InChIKey for a SMILES, or None on failure / empty result."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    key: str = Chem.MolToInchiKey(mol)  # type: ignore[no-untyped-call]
    return key or None


def _resolve_one(smiles: str | None) -> tuple[str | None, str | None]:
    """Run the layered resolver on a single SMILES.

    Returns ``(new_canonical_smiles, new_inchi_key)`` if resolved,
    ``(None, None)`` if not resolvable. Layer order (cheapest first):
    Layer A (R-group substitution). Layers B (ChEBI ontology) and C
    (EC-context inference) are added in subsequent iterations.
    """
    if not smiles or "[*]" not in smiles:
        return None, None
    new_smiles = substitute_wildcards(smiles)
    if new_smiles is None:
        return None, None
    new_key = _compute_inchi_key(new_smiles)
    if new_key is None:
        return None, None
    return new_smiles, new_key


def resolve_class_metabolites(df: pl.DataFrame) -> pl.DataFrame:
    """Resolve every wildcard-containing class metabolite to a concrete exemplar.

    Operates row-wise on a molecule DataFrame with the normalize-stage schema
    (mol_id, canonical_smiles, inchi_key, carbon_count, price_per_gram,
    source_refs). For each row where ``inchi_key`` is null AND
    ``canonical_smiles`` contains ``[*]``, runs the layered resolver and
    rewrites ``canonical_smiles`` + ``inchi_key`` in place. The ``mol_id``
    is preserved so reaction-table references still resolve.

    Adds an ``is_class_resolved`` boolean column flagging rewritten rows.
    Logs per-layer resolution counts at INFO level.
    """
    if df.height == 0:
        return df.with_columns(pl.lit(False, dtype=pl.Boolean).alias("is_class_resolved"))

    new_smiles_col: list[str | None] = []
    new_key_col: list[str | None] = []
    resolved_flags: list[bool] = []
    resolved_via_layer_a = 0

    for row in df.iter_rows(named=True):
        if row["inchi_key"] is not None or not row["canonical_smiles"]:
            new_smiles_col.append(row["canonical_smiles"])
            new_key_col.append(row["inchi_key"])
            resolved_flags.append(False)
            continue
        new_smiles, new_key = _resolve_one(row["canonical_smiles"])
        if new_smiles is None:
            new_smiles_col.append(row["canonical_smiles"])
            new_key_col.append(row["inchi_key"])
            resolved_flags.append(False)
            continue
        new_smiles_col.append(new_smiles)
        new_key_col.append(new_key)
        resolved_flags.append(True)
        resolved_via_layer_a += 1

    log.info(
        "resolve_class_metabolites: resolved %d / %d null-InChIKey rows via Layer A",
        resolved_via_layer_a,
        df.filter(pl.col("inchi_key").is_null()).height,
    )

    return df.with_columns(
        pl.Series("canonical_smiles", new_smiles_col, dtype=pl.Utf8),
        pl.Series("inchi_key", new_key_col, dtype=pl.Utf8),
        pl.Series("is_class_resolved", resolved_flags, dtype=pl.Boolean),
    )

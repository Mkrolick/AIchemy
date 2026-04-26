"""Tests for class-metabolite resolver (substituting [*] wildcards)."""

from __future__ import annotations

from pathlib import Path

import polars as pl
from rdkit import Chem

from aichemy.preprocessing.chem.resolve_class import (
    drop_unreferenced_empty_molecules,
    parse_chebi_obo,
    resolve_class_metabolites,
    resolve_via_chebi,
    substitute_wildcards,
)

FIXTURE_OBO = Path(__file__).parent.parent / "fixtures" / "chebi_mini.obo"


def _inchi_key(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    key = Chem.MolToInchiKey(mol)
    return key or None


def _make_mol_df(rows: list[dict]) -> pl.DataFrame:
    """Build a molecule DataFrame matching normalize.py's schema."""
    return pl.DataFrame(
        rows,
        schema={
            "mol_id": pl.Utf8,
            "canonical_smiles": pl.Utf8,
            "inchi_key": pl.Utf8,
            "carbon_count": pl.Int64,
            "price_per_gram": pl.Float64,
            "source_refs": pl.List(pl.Utf8),
        },
    )


class TestSubstituteWildcards:
    def test_returns_none_for_smiles_without_wildcards(self) -> None:
        # No [*], nothing to substitute — return None to signal "not applicable".
        assert substitute_wildcards("CCO") is None

    def test_returns_none_for_invalid_smiles(self) -> None:
        assert substitute_wildcards("not-a-smiles") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert substitute_wildcards("") is None

    def test_substitutes_single_wildcard_with_methyl(self) -> None:
        # [*]C(=O)O ("any acid") → methyl substitution → CC(=O)O (acetic acid)
        result = substitute_wildcards("[*]C(=O)O")
        assert result is not None
        # Must canonicalize to acetic acid's canonical form
        expected = Chem.MolToSmiles(Chem.MolFromSmiles("CC(=O)O"), canonical=True)
        assert result == expected

    def test_substitutes_multiple_wildcards(self) -> None:
        # [*]C(=O)N[*] → CC(=O)NC (N-methylacetamide)
        result = substitute_wildcards("[*]C(=O)N[*]")
        assert result is not None
        expected = Chem.MolToSmiles(Chem.MolFromSmiles("CC(=O)NC"), canonical=True)
        assert result == expected

    def test_substituted_smiles_yields_real_inchikey(self) -> None:
        # The whole point: post-substitution must produce a non-null InChIKey.
        result = substitute_wildcards("[*]C(=O)O")
        assert result is not None
        assert _inchi_key(result) is not None

    def test_real_metanetx_class_metabolite(self) -> None:
        # MNXM10032 (a class-level cephalosporin scaffold from MetaNetX)
        smiles = "[*]C(=O)N[C@]1([*])C(=O)N2C(C(=O)O)=C(CO)CSC21"
        result = substitute_wildcards(smiles)
        assert result is not None
        assert "[*]" not in result
        assert _inchi_key(result) is not None


class TestResolveClassMetabolites:
    def test_empty_df_returns_empty_with_column(self) -> None:
        empty = _make_mol_df([])
        out = resolve_class_metabolites(empty)
        assert out.height == 0
        assert "is_class_resolved" in out.columns
        assert out.schema["is_class_resolved"] == pl.Boolean

    def test_concrete_smiles_unchanged_and_marked_false(self) -> None:
        df = _make_mol_df(
            [
                {
                    "mol_id": "MNX001",
                    "canonical_smiles": "CCO",
                    "inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
                    "carbon_count": 2,
                    "price_per_gram": None,
                    "source_refs": ["MetaNetX:MNX001"],
                }
            ]
        )
        out = resolve_class_metabolites(df)
        row = out.row(0, named=True)
        assert row["canonical_smiles"] == "CCO"
        assert row["inchi_key"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
        assert row["is_class_resolved"] is False

    def test_wildcard_smiles_with_null_inchikey_is_resolved(self) -> None:
        df = _make_mol_df(
            [
                {
                    "mol_id": "MNXM10032",
                    "canonical_smiles": "[*]C(=O)O",
                    "inchi_key": None,
                    "carbon_count": None,
                    "price_per_gram": None,
                    "source_refs": ["MetaNetX:MNXM10032"],
                }
            ]
        )
        out = resolve_class_metabolites(df)
        row = out.row(0, named=True)
        assert row["is_class_resolved"] is True
        assert "[*]" not in row["canonical_smiles"]
        assert row["inchi_key"] is not None
        # mol_id must be preserved so reaction-table refs still resolve
        assert row["mol_id"] == "MNXM10032"

    def test_wildcard_smiles_with_existing_inchikey_is_left_alone(self) -> None:
        # If a row already has a valid InChIKey, do NOT touch it even if it has [*]
        df = _make_mol_df(
            [
                {
                    "mol_id": "MNX_OK",
                    "canonical_smiles": "[*]CC",
                    "inchi_key": "EXISTING-KEY-123",
                    "carbon_count": None,
                    "price_per_gram": None,
                    "source_refs": ["MetaNetX:MNX_OK"],
                }
            ]
        )
        out = resolve_class_metabolites(df)
        row = out.row(0, named=True)
        assert row["inchi_key"] == "EXISTING-KEY-123"
        assert row["canonical_smiles"] == "[*]CC"
        assert row["is_class_resolved"] is False

    def test_unresolvable_row_remains_null(self) -> None:
        # A SMILES with no [*] and null inchi_key — resolver shouldn't touch it
        # (Layer A only fires on [*]-containing SMILES).
        df = _make_mol_df(
            [
                {
                    "mol_id": "JUNK",
                    "canonical_smiles": "INVALID-SMILES-NO-WILDCARD",
                    "inchi_key": None,
                    "carbon_count": None,
                    "price_per_gram": None,
                    "source_refs": ["MetaNetX:JUNK"],
                }
            ]
        )
        out = resolve_class_metabolites(df)
        row = out.row(0, named=True)
        assert row["inchi_key"] is None
        assert row["is_class_resolved"] is False

    def test_mixed_batch(self) -> None:
        df = _make_mol_df(
            [
                {
                    "mol_id": "A",
                    "canonical_smiles": "CCO",
                    "inchi_key": "KEY-A",
                    "carbon_count": 2,
                    "price_per_gram": None,
                    "source_refs": ["MetaNetX:A"],
                },
                {
                    "mol_id": "B",
                    "canonical_smiles": "[*]C(=O)O",
                    "inchi_key": None,
                    "carbon_count": None,
                    "price_per_gram": None,
                    "source_refs": ["MetaNetX:B"],
                },
                {
                    "mol_id": "C",
                    "canonical_smiles": "[*]C(=O)N[*]",
                    "inchi_key": None,
                    "carbon_count": None,
                    "price_per_gram": None,
                    "source_refs": ["MetaNetX:C"],
                },
            ]
        )
        out = resolve_class_metabolites(df)
        flags = out["is_class_resolved"].to_list()
        assert flags == [False, True, True]
        # Both resolved rows must produce non-null InChIKey
        keys = out["inchi_key"].to_list()
        assert keys[0] == "KEY-A"
        assert keys[1] is not None
        assert keys[2] is not None


class TestDropUnreferencedEmptyMolecules:
    """Filter MetaNetX rows that have no SMILES AND aren't referenced by any reaction.

    These are MNX cross-reference catalog entries (chem_prop.tsv) that came in
    without structural data and aren't part of any reaction — pure dead weight
    for downstream stages. Rows with empty SMILES that ARE referenced by some
    reaction must NOT be dropped (would lose the reaction); they need a richer
    resolver to recover SMILES via cross-DB lookup.
    """

    def _make_rxn_df(self, rows: list[dict]) -> pl.DataFrame:
        return pl.DataFrame(
            rows,
            schema={
                "rxn_id": pl.Utf8,
                "reactants": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
                "products": pl.List(pl.Struct({"mol_id": pl.Utf8, "coefficient": pl.Float64})),
            },
        )

    def test_drops_empty_smiles_orphan(self) -> None:
        mols = _make_mol_df(
            [
                {
                    "mol_id": "MNX_ORPHAN",
                    "canonical_smiles": None,
                    "inchi_key": None,
                    "carbon_count": None,
                    "price_per_gram": None,
                    "source_refs": ["MetaNetX:MNX_ORPHAN"],
                }
            ]
        )
        rxns = self._make_rxn_df([])
        out = drop_unreferenced_empty_molecules(mols, rxns)
        assert out.height == 0

    def test_keeps_empty_smiles_referenced_by_reaction(self) -> None:
        mols = _make_mol_df(
            [
                {
                    "mol_id": "MNX_USED",
                    "canonical_smiles": None,
                    "inchi_key": None,
                    "carbon_count": None,
                    "price_per_gram": None,
                    "source_refs": ["MetaNetX:MNX_USED"],
                }
            ]
        )
        rxns = self._make_rxn_df(
            [
                {
                    "rxn_id": "R1",
                    "reactants": [{"mol_id": "MNX_USED", "coefficient": 1.0}],
                    "products": [{"mol_id": "OTHER", "coefficient": 1.0}],
                }
            ]
        )
        out = drop_unreferenced_empty_molecules(mols, rxns)
        assert out.height == 1
        assert out.row(0, named=True)["mol_id"] == "MNX_USED"

    def test_keeps_all_rows_with_nonempty_smiles(self) -> None:
        mols = _make_mol_df(
            [
                {
                    "mol_id": "A",
                    "canonical_smiles": "CCO",
                    "inchi_key": "KEY",
                    "carbon_count": 2,
                    "price_per_gram": None,
                    "source_refs": [],
                }
            ]
        )
        rxns = self._make_rxn_df([])
        out = drop_unreferenced_empty_molecules(mols, rxns)
        assert out.height == 1

    def test_treats_empty_string_as_empty(self) -> None:
        mols = _make_mol_df(
            [
                {
                    "mol_id": "EMPTY_STR",
                    "canonical_smiles": "",
                    "inchi_key": None,
                    "carbon_count": None,
                    "price_per_gram": None,
                    "source_refs": [],
                }
            ]
        )
        rxns = self._make_rxn_df([])
        out = drop_unreferenced_empty_molecules(mols, rxns)
        assert out.height == 0

    def test_handles_empty_reaction_table(self) -> None:
        # All molecules with non-empty SMILES kept; empty-SMILES dropped as orphans
        mols = _make_mol_df(
            [
                {
                    "mol_id": "REAL",
                    "canonical_smiles": "CCO",
                    "inchi_key": "KEY",
                    "carbon_count": 2,
                    "price_per_gram": None,
                    "source_refs": [],
                },
                {
                    "mol_id": "GHOST",
                    "canonical_smiles": None,
                    "inchi_key": None,
                    "carbon_count": None,
                    "price_per_gram": None,
                    "source_refs": [],
                },
            ]
        )
        rxns = self._make_rxn_df([])
        out = drop_unreferenced_empty_molecules(mols, rxns)
        ids = out["mol_id"].to_list()
        assert ids == ["REAL"]


class TestParseChebiObo:
    def test_parse_returns_id_to_smiles_and_isa_maps(self) -> None:
        parsed = parse_chebi_obo(FIXTURE_OBO)
        # Returns dict with 'smiles' and 'children' (or similar) keys
        assert "id_to_smiles" in parsed
        assert "children" in parsed
        # Concrete entries have SMILES
        assert parsed["id_to_smiles"]["CHEBI:15756"] == "CCCCCCCCCCCCCCCC(=O)O"
        # Class entries have no SMILES
        assert parsed["id_to_smiles"].get("CHEBI:35366") in (None, "")

    def test_parse_builds_children_index_from_is_a(self) -> None:
        parsed = parse_chebi_obo(FIXTURE_OBO)
        # CHEBI:35366 (fatty acid) has CHEBI:15756 and CHEBI:30823 as children
        children = set(parsed["children"].get("CHEBI:35366", []))
        assert children == {"CHEBI:15756", "CHEBI:30823"}


class TestResolveViaChebi:
    def test_returns_concrete_descendant_smiles(self) -> None:
        parsed = parse_chebi_obo(FIXTURE_OBO)
        # Asking for "fatty acid" should return one of its concrete descendants
        result = resolve_via_chebi("CHEBI:35366", parsed)
        assert result is not None
        assert result in (
            "CCCCCCCCCCCCCCCC(=O)O",
            r"CCCCCCCC/C=C\CCCCCCCC(=O)O",
        )

    def test_returns_none_for_unknown_id(self) -> None:
        parsed = parse_chebi_obo(FIXTURE_OBO)
        assert resolve_via_chebi("CHEBI:00000", parsed) is None

    def test_returns_none_for_class_with_no_concrete_descendants(self) -> None:
        parsed = parse_chebi_obo(FIXTURE_OBO)
        # CHEBI:99999 has no children
        assert resolve_via_chebi("CHEBI:99999", parsed) is None

    def test_returns_concrete_smiles_when_id_itself_is_concrete(self) -> None:
        parsed = parse_chebi_obo(FIXTURE_OBO)
        # Asking for palmitate directly returns its own SMILES
        result = resolve_via_chebi("CHEBI:15756", parsed)
        assert result == "CCCCCCCCCCCCCCCC(=O)O"

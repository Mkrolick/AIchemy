import polars as pl

from aichemy.preprocessing.io import REACTION_SCHEMA, Reaction


def test_reaction_schema_has_license_columns():
    assert REACTION_SCHEMA["patent_active"] == pl.Boolean
    assert REACTION_SCHEMA["process_covered"] == pl.Boolean
    assert REACTION_SCHEMA["composition_covered"] == pl.Boolean


def test_reaction_model_accepts_license_fields():
    r = Reaction(
        rxn_id="USPTO:7456123:0",
        reaction_smiles="C>>C",
        reactants=[{"mol_id": "M1", "coefficient": 1.0}],
        products=[{"mol_id": "M2", "coefficient": 1.0}],
        type="chemical",
        yield_rate=0.85,
        delta_g=None,
        balanced=True,
        source="uspto",
        patent_active=True,
        process_covered=True,
        composition_covered=False,
    )
    assert r.process_covered is True


def test_reaction_model_license_fields_default_false():
    r = Reaction(
        rxn_id="MNXR1",
        reaction_smiles="C>>C",
        reactants=[],
        products=[],
        type="enzymatic",
        yield_rate=0.85,
        delta_g=None,
        balanced=True,
        source="metanetx",
    )
    assert r.patent_active is False
    assert r.process_covered is False
    assert r.composition_covered is False

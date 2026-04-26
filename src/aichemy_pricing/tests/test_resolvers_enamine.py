"""Unit tests for EnamineSdfResolver."""
from __future__ import annotations

import textwrap

from aichemy_pricing.resolvers.enamine_sdf import EnamineSdfResolver


def test_resolver_indexes_at_least_one_enamine_sku(fixture_dir) -> None:
    res = EnamineSdfResolver.from_files([fixture_dir / "enamine_acids_snippet.sdf"])
    assert res.index, "expected at least one indexed InChIKey"
    sample_ik = next(iter(res.index))
    hits = res.resolve(sample_ik)
    for h in hits:
        assert h.vendor == "enamine"
        assert h.sku.startswith("EN300-")
        assert h.canonical_url == f"https://enaminestore.com/catalog/{h.sku}"


def test_resolver_normalizes_bare_id_to_en300_prefix(tmp_path) -> None:
    """If the SDF carries a bare numeric id (no EN300- prefix), the resolver
    must normalize it. Build a tiny synthetic SDF to exercise this path."""
    p = tmp_path / "tiny.sdf"
    p.write_text(textwrap.dedent("""\
        Foo
        ...
        > <InChIKey>
        BSYNRYMUTXBXSQ-UHFFFAOYSA-N

        > <Catalog ID>
        7605608

        $$$$
        """))
    res = EnamineSdfResolver.from_files([p])
    hits = res.resolve("BSYNRYMUTXBXSQ-UHFFFAOYSA-N")
    assert hits and hits[0].sku == "EN300-7605608"


def test_resolver_returns_empty_list_for_unknown_inchikey(fixture_dir) -> None:
    res = EnamineSdfResolver.from_files([fixture_dir / "enamine_acids_snippet.sdf"])
    assert res.resolve("ZZZZZZZZZZZZZZ-ZZZZZZZZZZ-Z") == []

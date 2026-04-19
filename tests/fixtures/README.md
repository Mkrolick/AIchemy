# Test Fixtures

Fixture data for integration tests. Kept tiny (≤20 rows each) and hand-curated.

Populated as stages are implemented:

- `metanetx_sample/` — `reac_prop.tsv`, `chem_prop.tsv`, `reac_xref.tsv` subset (added in the MetaNetX ingestion plan)
- `uspto_sample/` — reaction SMILES with known balance/yield (added in the USPTO ingestion plan)
- `known_duplicates.csv` — molecule pairs with expected dedup behavior (added in the dedup plan)

Do not commit large files here. Fixtures should round-trip in under 1 second.

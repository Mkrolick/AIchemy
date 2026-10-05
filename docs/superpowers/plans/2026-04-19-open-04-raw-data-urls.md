# Open Item 04 — Raw-data download URLs

**Goal:** Pin canonical download URLs for MetaNetX v4.4 and USPTO Lowe dataset (plus ZINC20 bulk for Stage 10).

**Needs user decision + verification.**

## Candidates

### MetaNetX v4.4
- `https://www.metanetx.org/ftp/4.4/reac_prop.tsv`
- `https://www.metanetx.org/ftp/4.4/chem_prop.tsv`
- `https://www.metanetx.org/ftp/4.4/reac_xref.tsv`
- `https://www.metanetx.org/ftp/4.4/chem_xref.tsv`

SHA256s: capture after first successful download.

### USPTO Lowe reactions (grants 1976–2016)
- Primary: `https://figshare.com/articles/dataset/Chemical_reactions_from_US_patents_1976-Sep2016_/5104873` — manual redirect, may require scraping figshare metadata for the actual download URL
- Alternative mirror: NextMove Software's site (may require registration)

### ZINC20 purchasable subset
- `https://zinc20.docking.org/substances/catalogs/zinc/` — paginated, may need scripted stitching, OR
- Bulk dump via `zinc20.docking.org/zinc20/downloads/` — SDF split by subset

## Tasks

- [ ] Verify MetaNetX URLs still resolve as of execution date
- [ ] Record SHA256 in config after verification
- [ ] Document figshare→Lowe extraction script (may require a manual download-then-upload step)
- [ ] Pin ZINC20 bulk URL and parse path
- [ ] Commit updated `configs/default.yaml` with these URLs + checksums

Unblocks Stage 01 (fetch-raw).

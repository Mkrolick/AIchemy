# CLAIM-04 — PubChem Substance SDF FTP dump

**Status:** PARTIAL

**Claim:** `ftp://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/` carries SourceName + RegistryID on every record, filterable to the **~700 vendor sources** listed at `pubchem.ncbi.nlm.nih.gov/sources/`.

## Verification steps performed

- [iter 4] curl `https://ftp.ncbi.nlm.nih.gov/pubchem/Substance/CURRENT-Full/SDF/` → 200 OK, real Apache directory listing. **982 `.sdf.gz` files**, each 60–120 MB, covering 500K SIDs each (~491M live SIDs). Recent timestamps confirm active mirror (e.g., `Substance_000500001_001000000.sdf.gz` updated 2026-04-20).
- [iter 4] Read `README-Substance-SDF` (1.6 KB, last touched 2019-11-24): confirms organization by SID range, points to `pubchem_sdtags.txt` for tag definitions.
- [iter 4] Pulled `https://ftp.ncbi.nlm.nih.gov/pubchem/specifications/pubchem_sdtags.txt`. Verbatim:
  ```
  PUBCHEM_EXT_DATASOURCE_NAME
      External Source/Database Name assigned by PubChem ...
  PUBCHEM_EXT_DATASOURCE_REGID
      External Registry ID for a Substance that is unique ...
  PUBCHEM_EXT_DATASOURCE_URL
  PUBCHEM_GENERIC_REGISTRY_NAME
  ```
- [iter 4] Hit PUG REST source-table endpoint:
  ```
  https://pubchem.ncbi.nlm.nih.gov/rest/pug/sourcetable/substance/JSON
  ```
  Returned a `Table.Row[]` with **914 sources total**. Categories (top-15):
  | Category | Count |
  |---|---|
  | Chemical Vendors, Legacy Depositors | 300 |
  | Chemical Vendors | 231 |
  | Legacy Depositors, Research and Development | 175 |
  | Research and Development | 75 |
  | Governmental Organizations | 19 |
  | Legacy Depositors, NIH Initiatives | 16 |
  | Governmental Organizations, Legacy Depositors | 15 |
  | Curation Efforts | 14 |
  | Curation Efforts, Research and Development | 14 |
  | Journal Publishers | 10 |
  | … | … |

  **Vendor-tagged sources: 231 + 300 = 531**, not "~700".

## Evidence

- FTP dump is real, fresh, anonymous, ~491M SIDs across 982 files.
- The vendor/registry fields claimed by the report exist but are named `PUBCHEM_EXT_DATASOURCE_NAME` and `PUBCHEM_EXT_DATASOURCE_REGID` — the report's "SourceName" / "RegistryID" are conceptual paraphrases, not literal SDF tag names.
- Total PubChem source count is **914**, not 700; vendor-tagged is **531** (231 active + 300 legacy).

## Verdict

**PARTIAL.** The architectural premise is sound — the bulk SDF dump exists, contains the vendor-mapping fields, and is anonymously downloadable. Two corrections:
1. **Tag names are `PUBCHEM_EXT_DATASOURCE_NAME` / `PUBCHEM_EXT_DATASOURCE_REGID`** (not "SourceName"/"RegistryID"). A scraper consuming the SDF must filter on these literal tag names.
2. **Source count ~914 total / 531 vendor-tagged**, not "~700 vendor sources". The "700" figure looks like an averaged hallucination between total and vendor-only counts.

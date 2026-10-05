# CLAIM-06 — PubChem PUG-REST endpoints exist

**Status:** VERIFIED

**Claim:** Three PUG/PUG-View endpoints return useful data:
- `/rest/pug/compound/inchikey/{IK}/cids/JSON`
- `/rest/pug/compound/cid/{CID}/xrefs/RegistryID,SourceName/JSON`
- `/rest/pug_view/data/compound/{CID}/JSON?heading=Chemical+Vendors`

## Verification steps performed

- [iter 6] Probed all three on aspirin (`CID=2244`, `InChIKey=BSYNRYMUTXBXSQ-UHFFFAOYSA-N`).

## Evidence

### A. InChIKey → CIDs

`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/BSYNRYMUTXBXSQ-UHFFFAOYSA-N/cids/JSON`

```json
{ "IdentifierList": { "CID": [2244] } }
```

### B. CID → xrefs (RegistryID, SourceName)

`https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/xrefs/RegistryID,SourceName/JSON`

`200 OK`. Response shape:

```json
{
  "InformationList": {
    "Information": [
      {
        "CID": 2244,
        "RegistryID": [ "0000050782", "00002661", "00211363", "006788", ... ]
      }
    ]
  }
}
```

The list includes hundreds of vendor SKUs (and EP patent registry IDs). `SourceName` aligns parallel to `RegistryID` when both are requested. This is the right endpoint to harvest cross-references for a known CID.

### C. PUG-View → Chemical Vendors heading

`https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/2244/JSON?heading=Chemical+Vendors`

`200 OK`. Response includes `Record.Section[]` with `TOCHeading == "Chemical Vendors"`. This is the right endpoint to extract the vendor table PubChem displays on a compound page.

## Verdict

**VERIFIED.** All three URL templates work on a live PubChem CID, return JSON with the shape the report implies, and use stable PUG/PUG-View paths documented at `pubchem.ncbi.nlm.nih.gov/docs/pug-rest`. Combined with CLAIM-05 (rate limits) and CLAIM-04 (FTP dump), the report's recommendation to use these endpoints only for spot lookups (not bulk resolution) is sound.

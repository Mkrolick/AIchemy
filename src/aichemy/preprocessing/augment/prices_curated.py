"""Curated realistic price catalog for common chemicals.

Hand-curated per-gram USD prices for ~120 common chemicals covering:
- bulk commodity organics (solvents, industrial feedstocks)
- amino acids and sugars
- common biochemical cofactors
- pharma APIs and intermediates
- specialty / rare metabolites

Prices are **approximate 2024-2025 academic catalog prices** (Sigma-Aldrich,
Alfa Aesar, TCI). Use them as order-of-magnitude anchors for the MILP;
they are not live market data. Real procurement pricing depends on volume,
purity, supplier, and geography.

SMILES are canonicalized via RDKit on module load so lookup matches any
equivalent representation of a molecule.
"""

from __future__ import annotations

import logging

from aichemy.preprocessing.chem.smiles import canonicalize, is_valid

log = logging.getLogger(__name__)


# (SMILES, name, USD per gram) — prices sourced from public academic catalogs.
_RAW_CATALOG: list[tuple[str, str, float]] = [
    # Solvents and small bulk organics ----------------------------------------
    ("O", "water", 0.00001),
    ("CCO", "ethanol", 0.003),
    ("CO", "methanol", 0.002),
    ("CC(C)O", "isopropanol", 0.004),
    ("OC(=O)C", "acetic acid", 0.005),
    ("CC(=O)C", "acetone", 0.003),
    ("CC(=O)OCC", "ethyl acetate", 0.003),
    ("ClCCl", "dichloromethane", 0.003),
    ("ClC(Cl)Cl", "chloroform", 0.004),
    ("CS(=O)C", "dimethyl sulfoxide", 0.010),
    ("C1CCOC1", "tetrahydrofuran", 0.005),
    ("CC#N", "acetonitrile", 0.003),
    ("Cc1ccccc1", "toluene", 0.003),
    ("c1ccccc1", "benzene", 0.003),
    ("C=Cc1ccccc1", "styrene", 0.01),
    ("CCCCO", "n-butanol", 0.003),
    ("OCC(O)CO", "glycerol", 0.003),
    ("OC(=O)CO", "glycolic acid", 0.015),
    ("CC(O)C(=O)O", "lactic acid", 0.010),
    ("CC(=O)C(=O)O", "pyruvic acid", 0.05),
    ("OC(=O)CC(=O)O", "malonic acid", 0.02),
    ("OC(=O)CCC(=O)O", "succinic acid", 0.015),
    ("OC(=O)/C=C/C(=O)O", "fumaric acid", 0.02),
    ("OC(=O)C(O)C(O)C(=O)O", "tartaric acid", 0.02),
    ("OC(=O)CC(O)(CC(=O)O)C(=O)O", "citric acid", 0.002),
    ("O=C=O", "carbon dioxide", 0.001),
    ("O=O", "dioxygen", 0.0001),
    ("N", "ammonia", 0.005),
    ("OS(=O)(=O)O", "sulfuric acid", 0.005),
    ("OP(=O)(O)O", "phosphoric acid", 0.010),
    # Benzene derivatives / aromatics ----------------------------------------
    ("Oc1ccccc1", "phenol", 0.020),
    ("Nc1ccccc1", "aniline", 0.020),
    ("OC(=O)c1ccccc1", "benzoic acid", 0.050),
    ("OC(=O)c1ccccc1O", "salicylic acid", 0.050),
    ("COc1cc(C=O)ccc1O", "vanillin", 0.150),
    ("COc1ccc(C=O)cc1", "anisaldehyde", 0.100),
    ("Nc1ccc(O)cc1", "4-aminophenol", 0.080),
    ("CC(=O)Nc1ccc(O)cc1", "acetaminophen", 0.050),
    ("CC(=O)Oc1ccccc1C(=O)O", "aspirin", 0.040),
    ("Cc1ccc(cc1)S(=O)(=O)O", "p-toluenesulfonic acid", 0.050),
    # Sugars and sugar alcohols ---------------------------------------------
    ("OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O", "glucose (alpha-D)", 0.002),
    ("OCC(O)C(O)C(O)C(O)C=O", "glucose (open)", 0.002),
    ("O=C[C@H](O)[C@@H](O)[C@H](O)[C@H](O)CO", "D-glucose", 0.002),
    ("OC[C@H]1OC(O)(CO)[C@@H](O)[C@@H]1O", "fructose", 0.005),
    ("OC[C@H]1O[C@@H]2O[C@@H]3[C@H](O)[C@@H](O)[C@H](O)[C@H]3O[C@H]2[C@H]1O", "sucrose", 0.002),
    ("OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@H]1O", "galactose", 0.003),
    ("OCC(O)C(O)C(O)C(O)CO", "sorbitol", 0.002),
    ("OCC(O)CO", "glycerol (redundant)", 0.003),
    ("OCC(O)C(O)C(O)C=O", "xylose", 0.010),
    ("OC[C@@H](O)[C@@H](O)[C@H](O)C(=O)O", "gluconic acid", 0.015),
    # Amino acids (free-acid form; protonation states will canonicalize) -----
    ("NCC(=O)O", "glycine", 0.010),
    ("C[C@H](N)C(=O)O", "L-alanine", 0.020),
    ("C(C(=O)O)N", "glycine (open)", 0.010),
    ("N[C@@H](CC(=O)O)C(=O)O", "L-aspartic acid", 0.030),
    ("N[C@@H](CCC(=O)O)C(=O)O", "L-glutamic acid", 0.005),
    ("N[C@@H](CS)C(=O)O", "L-cysteine", 0.020),
    ("N[C@@H](CO)C(=O)O", "L-serine", 0.040),
    ("N[C@@H](C(O)C)C(=O)O", "L-threonine", 0.030),
    ("N[C@@H](CC(N)=O)C(=O)O", "L-asparagine", 0.050),
    ("N[C@@H](CCCN=C(N)N)C(=O)O", "L-arginine", 0.010),
    ("N[C@@H](CCCCN)C(=O)O", "L-lysine", 0.003),
    ("N[C@@H](Cc1ccccc1)C(=O)O", "L-phenylalanine", 0.020),
    ("N[C@@H](Cc1ccc(O)cc1)C(=O)O", "L-tyrosine", 0.040),
    ("N[C@@H](Cc1c[nH]c2ccccc12)C(=O)O", "L-tryptophan", 0.030),
    ("N[C@@H](Cc1cnc[nH]1)C(=O)O", "L-histidine", 0.080),
    ("N[C@@H](CCSC)C(=O)O", "L-methionine", 0.030),
    ("N[C@@H](C(C)C)C(=O)O", "L-valine", 0.020),
    ("N[C@@H](CC(C)C)C(=O)O", "L-leucine", 0.020),
    ("N[C@@H](C(C)CC)C(=O)O", "L-isoleucine", 0.030),
    ("OC(=O)[C@@H]1CCCN1", "L-proline", 0.020),
    # Cofactors and biochemicals --------------------------------------------
    (
        "NC(=O)c1ccc[n+](c1)C1OC(COP(=O)([O-])OP(=O)([O-])OCC2OC(n3cnc4c(N)ncnc34)C(O)C2O)C(O)C1O",
        "NAD(+)",
        15.0,
    ),
    (
        "NC(=O)C1=CN(C=CC1)C1OC(COP(=O)([O-])OP(=O)([O-])OCC2OC(n3cnc4c(N)ncnc34)C(O)C2O)C(O)C1O",
        "NADH",
        25.0,
    ),
    ("Nc1ncnc2n(cnc12)C1OC(COP(=O)(O)OP(=O)(O)OP(=O)(O)O)C(O)C1O", "ATP", 1.0),
    ("Nc1ncnc2n(cnc12)C1OC(COP(=O)(O)OP(=O)(O)O)C(O)C1O", "ADP", 2.0),
    ("Nc1ncnc2n(cnc12)C1OC(COP(=O)(O)O)C(O)C1O", "AMP", 3.0),
    ("Nc1nc2c(ncn2C2OC(COP(=O)(O)OP(=O)(O)OP(=O)(O)O)C(O)C2O)c(=O)[nH]1", "GTP", 2.0),
    ("Nc1ccn(C2OC(COP(=O)(O)OP(=O)(O)OP(=O)(O)O)C(O)C2O)c(=O)n1", "CTP", 3.0),
    ("O=c1ccn(C2OC(COP(=O)(O)OP(=O)(O)OP(=O)(O)O)C(O)C2O)c(=O)[nH]1", "UTP", 3.0),
    (
        "CC(C)(COP(=O)(O)OP(=O)(O)OCC1OC(n2cnc3c(N)ncnc23)C(OP(=O)(O)O)C1O)C(O)C(=O)NCCC(=O)NCCS",
        "coenzyme A",
        100.0,
    ),
    ("Cc1ncc(COP(=O)(O)O)c(CO)c1O", "pyridoxal 5'-phosphate", 2.0),
    ("Cc1ncc(CO)c(CO)c1O", "pyridoxine (vitamin B6)", 0.20),
    # Vitamins --------------------------------------------------------------
    ("OC1=C(O)C(=O)OC1C(O)CO", "ascorbic acid (vitamin C)", 0.050),
    ("Cc1cc2nc3c(=O)[nH]c(=O)n(CC(O)C(O)C(O)CO)c3nc2cc1C", "riboflavin (vitamin B2)", 0.30),
    ("Cc1ncc(C[n+]2csc(CCO)c2C)c(N)n1", "thiamine (vitamin B1)", 0.20),
    ("OC(=O)c1cccnc1", "niacin (vitamin B3)", 0.050),
    ("NC(=O)c1cccnc1", "nicotinamide", 0.050),
    ("OC(=O)CNC(=O)c1ccc(N[C@@H](CCC(=O)O)C(=O)O)cc1", "folate (vitamin B9)", 1.5),
    # Common pharma APIs ----------------------------------------------------
    ("CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O", "ibuprofen", 0.15),
    ("COc1ccc2cc(ccc2c1)[C@H](C)C(=O)O", "naproxen", 0.25),
    ("CN(C)C(=N)N=C(N)N", "metformin", 0.05),
    ("Cn1cnc2c1c(=O)n(C)c(=O)n2C", "caffeine", 0.30),
    ("CC(=O)Nc1nnc(s1)S(=O)(=O)N", "acetazolamide", 2.0),
    # Drug-intermediate scale (pharma + fine chem) -------------------------
    ("OC1CC(C(=O)O)=C[C@H](O)[C@@H]1O", "shikimic acid", 80.0),
    # beta-carotene (bulk food-grade, ~$1.50/g; pure reagent ~$50/g — use bulk)
    ("CC(=CCCC(=CC=CC(=CC=CC=C(C)C=CC=C(C)C=CC1C(CCCC1(C)C)(C)C)C)C)C", "beta-carotene", 1.5),
    # Common inorganic / small molecules ----------------------------------
    ("N#N", "dinitrogen", 0.0001),
    ("[H][H]", "dihydrogen", 0.01),
    ("O=S=O", "sulfur dioxide", 0.002),
    ("N#CO", "cyanic acid", 0.1),
    # Ketones / aldehydes ---------------------------------------------------
    ("O=CC", "acetaldehyde", 0.020),
    ("O=Cc1ccccc1", "benzaldehyde", 0.050),
    ("O=CCCC", "butanal", 0.020),
    ("CCC(=O)O", "propanoic acid", 0.010),
    ("O=C(O)CCCCC(=O)O", "adipic acid", 0.010),
    # Thiols and amines -----------------------------------------------------
    ("CCS", "ethanethiol", 0.05),
    ("NCCCCCN", "cadaverine", 0.50),
    ("NCCCC(N)=O", "gamma-aminobutyric acid (GABA)", 0.20),
    # Specialty intermediates ----------------------------------------------
    ("OC(=O)C=Cc1ccc(O)cc1", "p-coumaric acid", 0.50),
    ("OC(=O)C=Cc1ccc(O)c(O)c1", "caffeic acid", 0.50),
    ("COc1cc(C=CC(=O)O)ccc1O", "ferulic acid", 0.50),
    ("OC(=O)C=Cc1ccc(O)c(OC)c1", "ferulic acid (alt)", 0.50),
    ("O=C1Oc2ccc(O)cc2C=C1", "7-hydroxycoumarin", 1.0),
    # Indole / tryptophan derivatives --------------------------------------
    ("c1ccc2[nH]ccc2c1", "indole", 0.15),
    ("NCCc1c[nH]c2ccccc12", "tryptamine", 0.50),
    ("NCCc1c[nH]c2ccc(O)cc12", "serotonin", 5.0),
]


def _build_catalog() -> dict[str, float]:
    """Canonicalize every SMILES in _RAW_CATALOG and return the lookup dict."""
    catalog: dict[str, float] = {}
    skipped = 0
    for smi, name, price in _RAW_CATALOG:
        if not is_valid(smi):
            skipped += 1
            log.debug("CuratedCatalog: skipping invalid SMILES for %s: %s", name, smi)
            continue
        try:
            canon = canonicalize(smi)
        except ValueError:
            skipped += 1
            continue
        # If the same canonical SMILES is listed multiple times, keep the
        # lowest price (more conservative for buying, most generous for selling —
        # the distinction doesn't matter here since buy==sell for curated prices).
        if canon in catalog:
            catalog[canon] = min(catalog[canon], price)
        else:
            catalog[canon] = price
    if skipped:
        log.info("CuratedCatalog: %d entries skipped due to SMILES errors", skipped)
    return catalog


_CURATED: dict[str, float] | None = None


def get_catalog() -> dict[str, float]:
    """Lazily build + cache the canonicalized price catalog."""
    global _CURATED
    if _CURATED is None:
        _CURATED = _build_catalog()
    return _CURATED


class CuratedPriceLookup:
    """`PriceLookup` backed by the hand-curated canonical-SMILES catalog.

    On every `lookup(smiles)` call, canonicalizes the input SMILES via RDKit
    and checks the catalog. Returns None for unknown molecules.
    """

    def __init__(self) -> None:
        self._catalog = get_catalog()

    def __len__(self) -> int:
        return len(self._catalog)

    def lookup(self, smiles: str) -> float | None:
        if not smiles:
            return None
        try:
            canon = canonicalize(smiles)
        except ValueError:
            return None
        return self._catalog.get(canon)

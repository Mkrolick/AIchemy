# minChemBio: Expanding Chemical Synthesis with Chemo-Enzymatic Pathways Using Minimal Transitions

## Research Report

**Date Generated:** February 26, 2026

---

## Full Citation

Anand, M., Upadhyay, V., & Maranas, C. D. (2025). minChemBio: Expanding Chemical Synthesis with Chemo-Enzymatic Pathways Using Minimal Transitions. *ACS Synthetic Biology*, 14(3), 756-770.

- **DOI:** [10.1021/acssynbio.4c00692](https://doi.org/10.1021/acssynbio.4c00692)
- **PMID:** 39951253
- **PMCID:** PMC11934129
- **Online Publication:** February 14, 2025
- **Print Publication:** March 21, 2025

### Author Affiliations

All authors are affiliated with:
- The Pennsylvania State University, State College, Pennsylvania 16802, United States

---

## Abstract / Overview

Chemo-enzymatic pathway design aims to combine the strengths of enzymatic and chemical synthesis to traverse biomolecular design space more efficiently. While chemical reactions often struggle with regioselectivity and stereoselectivity, enzymatic conversions often encounter limitations of low enzyme activity or availability. Optimally integrating both approaches provides an opportunity to identify efficient pathways beyond the capabilities of either modality.

The authors introduce **minChemBio**, an algorithmic approach that relies on solving a mixed-integer linear programming (MILP) problem by optimally searching through known chemical and enzymatic steps extracted from the United States Patent Office (USPTO) and MetaNetX databases. minChemBio allows for the minimization of transitions between chemical and biological reactions in the pathway, thus reducing the need for costly separation and purification steps required when switching between reaction modalities.

minChemBio was benchmarked on three case studies involving the synthesis of:
1. 2,5-furandicarboxylic acid (FDCA)
2. Terephthalate (TPA)
3. (R)-3-Hydroxybutyrate

Identified designs included both established literature pathways as well as unexplored ones, which were compared against pathways identified by existing retrosynthetic tools (ASKCOS, RetroBioCat).

---

## Key Methodology

### MILP Formulation

minChemBio formulates pathway design as an optimization problem that minimizes transitions between chemical catalysis and biocatalytic steps.

#### Objective Function
```
Minimize: sum(x_i + y_i + z_i) for all intermediates i
```

Where:
- **x_i**: Binary indicator for chemical-to-biological transitions at intermediate i
- **y_i**: Binary indicator for biological-to-chemical transitions at intermediate i
- **z_i**: Binary indicator for chemical-to-chemical transitions at intermediate i

#### Key Decision Variables
- **v_j**: Flux through reaction mapping j (nonzero if reaction is active in pathway)
- Binary transition indicators as described above

#### Critical Constraints
1. **Molecule Balance:** All intermediates produced must be consumed (mass balance)
2. **Thermodynamic Consistency:** Opposite directional mappings from the same reaction cannot coexist in a pathway
3. **Transition Identification:** Products detected at module boundaries trigger separation requirements
4. **Solution Enumeration:** Constraint 17 removes previous optimal solutions to identify alternate pathways

The MILP can yield multiple solutions (e.g., 23 solutions within 2 hours for p-Xylene to terephthalate). Suboptimal solutions are also valuable because longer pathways may have better thermodynamic feasibility or avoid difficult cosubstrate requirements.

### Reaction Databases

#### USPTO Chemical Reactions
- **Starting Dataset:** ~1.8 million reactions, 1.2 million molecules
- **After Preprocessing:** 1,135,706 one-to-one mappings
- **Preprocessing Steps:**
  - Remove duplicates
  - Assign unique identifiers to overlapping chemicals
  - Remove reactions without hydrocarbons in reactant or product sets
  - Handle unbalanced reactions by tracking "main carbon path" rather than full stoichiometry

#### MetaNetX Biological Reactions
- **Initial Dataset:** 57,541 reactions
- **Final Dataset:** 67,622 unique directional mappings
- **Preprocessing:**
  - Remove 47 common cofactors (CO2, H2O, ATP, NAD+, etc.) before mapping
  - Support both forward and reverse reaction directions

### One-to-One Mapping Strategy

The tool extracts primary reactant-product pairs using **Tanimoto similarity coefficients** to identify which reactant transforms into which product, enabling tracking of the main carbon path through multi-substrate reactions.

### Thermodynamic Assessment

The study employed **dGPredictor** to evaluate enzymatic step feasibility at pH 7.0 and ionic strength 0.1M. Example findings:
- 5-HMF oxidase: Highly favorable (-453 kJ/mol)
- Acetyl-CoA C-acetyltransferase: Thermodynamically challenging (+26.31 kJ/mol)

---

## Main Results and Contributions

### Case Study 1: 2,5-Furandicarboxylic Acid (FDCA)

FDCA is a bioplastic precursor that can be synthesized from glucose.

- **Results:** 23 pathways identified from glucose
- **Key Finding:** Three-step pathway with isomerization-cyclization-oxidation sequence
- **Comparison:** ASKCOS and RetroBioCat only generated routes through expensive precursors
- **Thermodynamics:** Pathway 1 showed all favorable steps; Pathway 2 had one mildly endergonic step (+13.4 kJ/mol)

### Case Study 2: Terephthalate (TPA)

TPA is a major polyester precursor currently produced via the energy-intensive AMOCO process.

- **Results:** 21 pathways from p-xylene; 8 distinct routes identified
- **Innovation:** Five previously unexplored chemo-enzymatic pathways discovered
- **Trade-offs:** Fully enzymatic pathway (6 steps) faces thermodynamic challenges vs. hybrid routes requiring fewer steps but additional transitions
- **Industrial Context:** Alternatives identified that could reduce metal catalyst and energy requirements

### Case Study 3: (R)-3-Hydroxybutyrate

- **Results:** 21 pathways from pyruvate; 24 pathways from glycerol
- **Discovery:** Two-step aminotransferase pathway (Pathway 1) not previously documented in literature

### Key Advantages Over Existing Tools

1. **Transition Minimization:** Explicitly reduces separation/purification costs by minimizing chemical-biological switches
2. **Flexible Starting Materials:** Allows user specification of starting materials (not limited to purchasable chemicals)
3. **Novel Discovery:** Identifies pathways inaccessible to template-based approaches like ASKCOS and RetroBioCat
4. **Multiple Solutions:** Generates numerous alternative pathways for evaluation

---

## Limitations

### Technical Limitations

1. **Major/Minor Product Distinction:** Cannot distinguish major from minor products due to USPTO SMILES format lacking this annotation. This can lead to incorrect primary product assignments.

2. **Transferase Reaction Tracking:** Transferase reactions may track cosubstrate paths rather than the main reactant carbon path, leading to solutions that do not follow the intended molecular transformation.

3. **Database Annotation Errors:** Incorrect annotations in USPTO database result in erroneous one-to-one mappings. Example: misannotated agents appearing as coreactants/coproducts cause incorrect Tanimoto coefficient mappings.

4. **Known Reactions Only:** The tool relies solely on known reactions from USPTO and MetaNetX; it cannot propose novel reaction steps or enzyme functions.

5. **Manual Validation Required:** Patent literature validation is needed for correctly annotated reactions, requiring manual verification of generated pathways.

### Methodological Limitations

6. **No Real Cost Modeling:** The optimization minimizes transitions as a proxy for cost, but does not incorporate:
   - Actual reagent/catalyst costs
   - Equipment and operational costs
   - Yield considerations
   - Scale-up economics
   - Enzyme production costs

7. **No Sensitivity Analysis:** The paper does not include systematic sensitivity analysis examining:
   - Parameter sensitivity in the MILP formulation
   - Robustness of optimal solutions to database changes
   - Impact of preprocessing threshold choices

8. **Thermodynamic Assessment Limitations:** While dGPredictor is used for evaluation, thermodynamic feasibility is assessed post-hoc rather than integrated into the optimization objective.

### Future Work Suggestions (from authors)

- Use of Large Language Models (LLMs) to validate reaction SMILES annotations and improve database quality
- Integration with experimental validation pipelines

---

## Code Repositories and Data Availability

### GitHub Repository

**URL:** [https://github.com/maranasgroup/chemo-enz](https://github.com/maranasgroup/chemo-enz)

**License:** MIT License

**Dependencies:**
- Python 3.11
- RDKit (chemistry toolkit)
- Streamlit (web interface)
- Pandas, NumPy (data handling)
- NetworkX (graph algorithms)
- Matplotlib (visualization)
- PuLP (MILP modeling)
- CPLEX solver (optimization engine)

**Installation:**
```bash
conda env create -f minchembio_yml.yml
```

**Usage Options:**
1. Web Interface: `streamlit run minchembio_streamlit.py`
2. Command-line: `python minchembio.py` (edit main() with molecule IDs)
3. Jupyter notebook for visualization

### Supplementary Data Repository

**URL:** [ScholarSphere - Penn State](https://scholarsphere.psu.edu/resources/2a44eb54-429a-4432-8ca3-9f3e9c9a668d)

**DOI:** [10.26207/tbg0-gr88](https://doi.org/10.26207/tbg0-gr88)

**Contents:**
- minChemBio_codes_data.zip (284 MB) - Complete codes and datasets
- README.txt - Documentation
- Five essential JSON files mapping molecules to reactions
- SMILES-to-ID dictionaries

**Note:** Large data files are hosted on ScholarSphere rather than GitHub due to 100MB file size limitations.

---

## Access Options

| Source | URL | Access Type |
|--------|-----|-------------|
| ACS Publications | [pubs.acs.org](https://pubs.acs.org/doi/10.1021/acssynbio.4c00692) | Journal (Subscription/OA) |
| PubMed Central | [PMC11934129](https://pmc.ncbi.nlm.nih.gov/articles/PMC11934129/) | Free Full Text |
| PubMed | [39951253](https://pubmed.ncbi.nlm.nih.gov/39951253/) | Abstract |
| ScienceDirect | [Link](https://www.sciencedirect.com/org/science/article/pii/S2161506325000439) | Alternative Access |

**Note:** No arXiv preprint was identified for this paper. The work was published directly in ACS Synthetic Biology.

---

## Related Commentary

A research highlight discussing minChemBio was published in Nature Chemical Biology:
- "Guiding chemoenzymatic synthesis" - [Nature Chemical Biology](https://www.nature.com/articles/s41589-025-01876-6)

---

## Conference Presentation

The work was also presented at AIChE 2025:
- "Minchembio: Chemo-Enzymatic Pathway Design for Chemical Synthesis with Minimal Transitions" - [AIChE 2025](https://aiche.confex.com/aiche/2025/prelim.cgi/Paper/718143)

---

## Summary

minChemBio represents a significant contribution to computational pathway design by explicitly optimizing for minimal transitions between chemical and biological synthesis modalities. The MILP-based approach, combined with comprehensive reaction databases from USPTO and MetaNetX, enables discovery of novel chemo-enzymatic routes that existing tools miss. While the tool has limitations in cost modeling and relies on database quality, its open-source availability and demonstrated success on industrially relevant targets (FDCA, TPA, 3-hydroxybutyrate) make it a valuable addition to the retrosynthesis toolkit.

---

*Report generated for AIchemy research documentation.*

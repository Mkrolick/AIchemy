# ASKCOS with Enzymatic Extensions: Comprehensive Research Report

## Paper: Merging Enzymatic and Synthetic Chemistry with Computational Synthesis Planning

---

## Full Citation

**Levin, I., Liu, M., Voigt, C. A., & Coley, C. W.** (2022). Merging enzymatic and synthetic chemistry with computational synthesis planning. *Nature Communications*, 13(1), 7747.

- **DOI:** [10.1038/s41467-022-35422-y](https://doi.org/10.1038/s41467-022-35422-y)
- **PMID:** 36517480
- **Published:** December 14, 2022
- **Journal:** Nature Communications (Open Access)

**Authors and Affiliations:**
- Itai Levin - Massachusetts Institute of Technology
- Mengjie Liu - Massachusetts Institute of Technology
- Christopher A. Voigt - Massachusetts Institute of Technology
- Connor W. Coley - Massachusetts Institute of Technology

---

## Abstract / Overview

Synthesis planning programs trained on chemical reaction data can design efficient routes to new molecules of interest, but are limited in their ability to leverage rare chemical transformations. This challenge is particularly acute for enzymatic reactions, which are valuable due to their selectivity and sustainability but are fewer in number compared to synthetic organic reactions.

The authors report a retrosynthetic search algorithm using **two neural network models for retrosynthesis**:
- One covering **7,984 enzymatic transformations**
- One covering **163,723 synthetic transformations**

The algorithm balances the exploration of enzymatic and synthetic reactions to identify hybrid synthesis plans. This approach:
1. Extends the space of retrosynthetic moves by thousands of uniquely enzymatic one-step transformations
2. Discovers routes to molecules for which synthetic-only or enzymatic-only searches find none
3. Designs shorter routes for certain target molecules

**Case Studies:** Application to (-)-Delta-9 tetrahydrocannabinol (THC/dronabinol) and R,R-formoterol (arformoterol) demonstrates how the strategy facilitates replacement of metal catalysis, reduces step counts, and eliminates costly enantiomeric resolution with more elegant hybrid proposals.

---

## Key Methodology

### 1. Multi-Model Tree Search Algorithm

The core innovation extends ASKCOS's tree search algorithm to use multiple template prioritizer models rather than a single one. At each step of retrosynthetic expansion, moves from either template set (enzymatic or synthetic) can be selected.

**Key Features:**
- Uses softmax normalization to allow direct comparison between enzymatic and synthetic template suggestions
- Prevents the broader synthetic chemistry set (~164K templates) from dominating over the smaller enzymatic set (~8K templates)
- Arbitrarily many models can guide a single search

### 2. MCTS (Monte Carlo Tree Search) Integration

The system employs the MCTS-based multistep chemical synthesis planning tool in ASKCOS:

**Algorithm Components:**
1. **Selection:** Uses Upper Confidence bounds applied to Trees (UCT) equation
2. **Expansion:** Neural network predicts and ranks which reaction templates most apply to the target molecule
3. **Simulation:** Recursive retrosynthetic expansion
4. **Backpropagation:** Scores propagated back to update tree

**Search Parameters:**
- Typical runtime: ~2 minutes per target
- Maximum depth: typically 5 steps
- Termination: Fixed number of iterations or time limit reached

### 3. Retro* Algorithm

The paper references Retro*, a neural-guided A* search algorithm for retrosynthetic planning, as an alternative tree search method available in ASKCOS. This provides:
- More informed heuristic guidance
- Provably optimal path finding (under certain assumptions)
- Different exploration-exploitation tradeoff than MCTS

### 4. Enzymatic Template Integration

**Data Source:** BKMS (Braunschweig Enzyme Database) composite database
- Contains ~37,000 enzyme-catalyzed reactions
- Aggregated from BRENDA, KEGG, Metacyc, and SABIO-RK

**Template Extraction Process:**
1. Removed biological cofactors from reactions
2. Converted reactions to standardized SMILES strings
3. Performed atom-atom mapping
4. Extracted reaction templates using RDChiral as generalized SMARTS strings

**Results:**
- 15,309 unique enzymatic reactions processed
- **7,984 unique reaction templates** extracted
- ~80% of enzymatic templates had only single precedent examples
- Templates were NOT filtered by frequency to preserve chemical diversity

**Unique Chemistry Identified:**
- Of 14,601 non-spontaneous reactions analyzed, 5,506 (corresponding to 4,169 templates) could not be reproduced using synthetic Reaxys templates
- At least 824 templates represent genuinely enzymatic transformations not captured by synthetic databases

### 5. Synthetic Template Database

The synthetic retrosynthesis model uses templates from:
- **Reaxys database:** 12.4-12.5 million single-step synthetic reactions
- **163,723 generalized reaction rules** summarizing retrosynthetic transformations
- Feedforward neural network ranks template applicability

### 6. Buyable Compounds Database

The ASKCOS buyable compounds database serves as the termination condition for retrosynthetic search:

**Database Contents:**
- Default: ~280,000-313,458 compounds
- Sources: eMolecules, LabNetwork, Sigma-Aldrich, Mcule, ChemBridge
- Price threshold: Typically compounds available for less than $100/g
- Users can add custom building blocks

**Termination Criteria:**
- Search terminates when a precursor matches a buyable compound
- Routes are evaluated based on reaching commercially available starting materials

---

## Main Results and Contributions

### Benchmark Results (1,000 ZINC molecules)

| Search Type | Molecules with Pathways Found |
|-------------|------------------------------|
| Enzymatic-only | 317 |
| Synthetic-only | 535 |
| Hybrid search | 493 |

**Key Findings:**
- Hybrid search discovered routes to **56 molecules** unreachable by synthetic-only search
- **15 molecules** required enzymatic steps absent from synthetic databases
- While hybrid underperformed synthetic alone under time constraints, it provides unique chemistry access

### Route Quality Improvements

When comparing hybrid and synthetic routes to identical targets:
- **73 molecules (17%)**: Hybrid found shorter pathways (counting individual enzymatic steps)
- **116 molecules (27%)**: Hybrid found shorter pathways (counting consecutive enzymatic reactions as single steps)

### Case Study 1: Dronabinol (THC)

The algorithm proposed a hybrid route involving:
1. Horner-Wadsworth-Emmons chemistry
2. Aluminum-catalyzed alkylation
3. **Enzymatic ring closure** via tetrahydrocannabinolic acid synthase

**Advantage:** Eliminates need for transition-metal catalysts required in purely synthetic approaches.

### Case Study 2: Arformoterol

The system suggested using **lysine 5,6-aminomutase** for chiral amine formation:
- Identified as a "unique enzymatic transformation" lacking synthetic precedent
- Proposed cascade approach potentially enables one-pot synthesis
- Eliminates intermediate isolation steps

### Novel Contributions

1. **First integrated hybrid planner:** Seamlessly combines enzymatic and synthetic chemistry in a single search
2. **Expanded chemical space:** Added 4,169 unique enzymatic templates not covered by synthetic databases
3. **Template calibration method:** Softmax normalization enables fair comparison between template sets of different sizes
4. **Practical demonstrations:** Showed real-world applicability through pharmaceutical case studies

---

## Limitations

### 1. Lack of MILP Optimization

The paper uses heuristic tree search algorithms (MCTS, Retro*) rather than Mixed Integer Linear Programming (MILP) optimization:
- **No global optimality guarantees** for route selection
- Cannot simultaneously optimize multiple objectives (cost, steps, yield) in a formally optimal way
- Route ranking relies on heuristic scoring rather than proven optimal solutions

### 2. No Formal Sensitivity Analysis

The methodology lacks:
- Systematic analysis of how results change with parameter variations
- Robustness testing across different hyperparameter settings
- Uncertainty quantification for route predictions

### 3. Model Calibration Challenges

The approach relies on both models producing appropriately scaled probability scores:
- Testing confirmed enzymatic templates appeared in top-3 suggestions for 88-96% of small molecules
- Synthetic templates appeared for 95-99%
- However, calibration may not generalize to all molecular classes

### 4. Search Space Expansion Trade-offs

Including more templates increases computational branching:
- Hybrid searches sometimes explore unproductive directions
- May underperform synthetic-only search under identical wall-clock time limits
- Requires longer search times to realize benefits

### 5. Template Generalization Limitations

Rare templates with single examples limit model generalization:
- Authors note that "defining enzyme reaction templates at a physically meaningful level of generality may require additional information, such as reaction mechanism or binding pocket structure"
- Current template extraction is purely structure-based

### 6. Enzyme Engineering Assessment Gap

A significant practical limitation:
- Determining whether enzymes could plausibly be engineered for suggested reactions remains challenging
- Authors state this "still requires expert knowledge, intuition, and experimentation"
- Models for predicting enzyme-substrate compatibility "generalize poorly even in relatively data-rich regimes"

### 7. Data Availability Constraints

- The proprietary Reaxys dataset cannot be shared
- Enzymatic reaction databases are smaller and sparser than synthetic databases
- Template coverage is uneven across enzyme classes

---

## Code Repositories and Data Availability

### Primary Repositories

| Repository | Description | URL |
|------------|-------------|-----|
| **hybmind** | Analysis scripts and Jupyter notebooks | [github.com/itai-levin/hybmind](https://github.com/itai-levin/hybmind) |
| **chemoenzymatic-askcos** | Modified ASKCOS deployment | [github.com/itai-levin/chemoenzymatic-askcos](https://github.com/itai-levin/chemoenzymatic-askcos) |
| **bkms-data** | Processed BKMS enzymatic templates | [github.com/itai-levin/bkms-data](https://github.com/itai-levin/bkms-data) |

### Repository Details

#### hybmind
- **Purpose:** Data processing and analysis for the manuscript
- **Contents:**
  - `process_BKMS_database/` - Extract reaction SMILES, remove cofactors, atom-atom mapping
  - `train-model/` - Hyperparameter optimization and model training
  - `analyze_templates/` - Template precedent counting and comparison
  - `call_ASKCOS_api/` - Pathway search request submission
  - `process_ASKCOS_results/` - Synthesis route extraction
- **License:** MIT
- **Dependencies:** rdkit 2020.03.2, pandas 1.0.5, tensorflow 2.1.0, numpy 1.19.5

#### chemoenzymatic-askcos
- **Purpose:** Deployment of modified ASKCOS with enzymatic capabilities
- **Requirements:**
  - Ubuntu 18.04 LTS or later
  - Minimum 4 vCPUs, 26 GB RAM, 100 GB disk
  - Docker and Docker Compose
  - Git LFS
- **License:** Mozilla Public License 2.0 (MPL-2.0)
- **Note:** Now migrated to GitLab for ongoing development

#### bkms-data
- **Purpose:** Processed enzymatic template data for ASKCOS integration
- **Contents:**
  - `models/bkms/1/` - Trained model files
  - `reactions/` - Processed reaction data
  - `templates/` - Extracted template files
- **License:** MIT

### Related Resources

- **ASKCOS Documentation:** [askcos-docs.mit.edu](https://askcos-docs.mit.edu/)
- **ASKCOS Main Repository:** [github.com/ASKCOS/ASKCOS](https://github.com/ASKCOS/ASKCOS)
- **Template Functions:** [gitlab.com/mefortunato/template-relevance](https://gitlab.com/mefortunato/template-relevance)

---

## Summary

The Levin et al. 2022 paper represents a significant advancement in computer-aided synthesis planning by integrating enzymatic transformations alongside traditional synthetic chemistry within a unified retrosynthetic search framework. The key innovation is the multi-model tree search algorithm that balances exploration across both reaction domains using calibrated neural network models.

**Strengths:**
- Expands accessible chemical space with 4,169+ unique enzymatic templates
- Discovers routes inaccessible to single-domain searches
- Demonstrates practical value through pharmaceutical case studies
- Open-source implementation available

**Weaknesses:**
- Heuristic rather than globally optimal search (no MILP)
- No formal sensitivity or uncertainty analysis
- Limited enzyme engineering feasibility assessment
- Smaller enzymatic template database compared to synthetic

The work establishes a foundation for hybrid chemoenzymatic synthesis planning and highlights the potential for enzymatic reactions to complement traditional synthetic chemistry in route design.

---

## References

1. Levin, I., Liu, M., Voigt, C. A., & Coley, C. W. (2022). Merging enzymatic and synthetic chemistry with computational synthesis planning. *Nature Communications*, 13(1), 7747.
2. Segler, M. H., Preuss, M., & Waller, M. P. (2018). Planning chemical syntheses with deep neural networks and symbolic AI. *Nature*, 555(7698), 604-610.
3. Chen, B., Li, C., Dai, H., & Song, L. (2020). Retro*: Learning retrosynthetic planning with neural guided A* search. *ICML 2020*.
4. Coley, C. W., et al. (2017). Computer-assisted retrosynthesis based on molecular similarity. *ACS Central Science*, 3(12), 1237-1245.

---

*Report generated: February 2026*
*Source: Nature Communications, PubMed Central, GitHub repositories*

# SPARROW: An Algorithmic Framework for Synthetic Cost-Aware Decision Making in Molecular Design

## Research Report

**Date Generated:** February 26, 2026

---

## Full Citation

**Authors:** Jenna C. Fromer, Connor W. Coley

**Title:** An algorithmic framework for synthetic cost-aware decision making in molecular design

**Journal:** Nature Computational Science

**Volume:** 4, Issue 6

**Pages:** 440-450

**Publication Date:** June 17, 2024

**DOI:** [10.1038/s43588-024-00639-y](https://doi.org/10.1038/s43588-024-00639-y)

**PMID:** 38886590

**arXiv Preprint:** [arXiv:2311.02187](https://arxiv.org/abs/2311.02187) (submitted November 3, 2023; last revised May 28, 2024)

**Author Affiliations:**
- MIT Department of Chemical Engineering
- MIT Department of Electrical Engineering and Computer Science

**Funding:** DARPA Accelerated Molecular Discovery program, Office of Naval Research

---

## Abstract/Overview

Small molecules exhibiting desirable property profiles are often discovered through an iterative process of designing, synthesizing, and testing sets of molecules. The selection of molecules to synthesize from all possible candidates is a complex decision-making process that typically relies on expert chemist intuition.

The authors propose **SPARROW** (**S**ynthesis **P**lanning **A**nd **R**ewards-based **R**oute **O**ptimization **W**orkflow), a quantitative decision-making framework that prioritizes molecules for evaluation by balancing expected information gain and synthetic cost. SPARROW integrates molecular design, property prediction, and retrosynthetic planning to balance the utility of testing a molecule with the cost of batch synthesis.

The key innovation is capturing the **non-additive costs inherent to batch synthesis**--recognizing that synthesizing multiple molecules together can be more efficient than making them individually by leveraging common reaction steps and intermediates.

---

## Key Methodology

### Overview of the Workflow

SPARROW performs seven sequential steps:
1. Retrosynthetic tree search via ASKCOS
2. Integration of routes into a unified synthesis network (RouteGraph)
3. Reaction confidence scoring using ASKCOS forward predictor
4. Optimization variable definition (PuLP or Gurobi)
5. Constraint and objective function specification
6. Problem solving
7. Route and molecule selection output

### MILP Formulation

#### Decision Variables
SPARROW employs **two sets of binary decision variables** that indicate whether each compound node and each reaction node is included in any of the selected synthetic routes.

#### Objective Function
The framework defines a **weighted sum objective function** comprised of three terms:

1. **Cumulative rewards** of selected candidate molecules (maximize)
2. **Cost of purchased starting materials** (minimize)
3. **Number of reactions and their likelihood of success** (minimize reaction penalties inversely proportional to success probabilities)

The objective function is formulated as:
```
maximize: λ₁(cumulative rewards) - λ₂(starting material costs) - λ₃(reaction penalties)
```

Where λ₁, λ₂, λ₃ are adjustable **weighting factors** that allow users to adjust the relative importance of utility versus cost considerations.

#### Constraints (Three Primary)

1. **Reactant Availability Constraint:** All parent nodes of a selected reaction node must also be selected
2. **Product Synthesis Constraint:** If a compound is selected, at least one reaction that produces it must also be selected
3. **Cycle Prevention Constraint:** Forbids the selection of synthetic cycles in the retrosynthetic graph that do not originate from buyable compounds

#### Solver
The optimization uses **PuLP** with the open-source **COIN-OR branch-and-cut (CBC) solver**. The optimization problem itself typically solves within seconds, though numerical instability can occur when weighting factors span multiple orders of magnitude.

For nonlinear problems (expected reward formulation), **Gurobi** is supported with the `--prune-distance` parameter.

### ChemSpace API Integration

SPARROW determines the **buyability of each compound and its cost** using the ChemSpace API:

- Queries availability and pricing (study used data as of October 2023)
- Identifies commercially available starting materials and their per-gram costs
- Enables SPARROW to decide whether buying a molecule or synthesizing it from cheaper precursors makes better economic sense
- Adds "dummy parent reaction nodes producing each buyable compound" to enable buy-versus-synthesize decisions

**Configuration:** Users must obtain a ChemSpace API key and enter it in `keys.py`, then specify `--key-path` when running SPARROW with ChemSpace as the coster.

The authors validated their October 2023 pricing against March 2024 ChemSpace data, confirming "cost discrepancies are minor and do not artificially boost SPARROW's performance relative to baselines."

### ASKCOS Integration

ASKCOS (Automated System for Knowledge-based Computer-aided Organic Synthesis) serves as the retrosynthesis engine:

- **Retrosynthetic Tree Search:** Generates retrosynthetic trees with an expansion time of 60 seconds
- **Context Recommender:** Proposes reaction conditions
- **Forward Predictor Model:** Estimates the probability of reaction success for each reaction
- **Plausibility Scoring:** Assigns plausibility scores to proposed synthetic routes

**Two deployment versions supported:**
- ASKCOSv2 (`api`)
- ASKCOSv1 (`apiv1`)

Specified via `--path-finder`, `--recommender`, and `--scorer` arguments.

**ASKCOS Web Interface:** https://askcos.mit.edu/

---

## Case Studies and Main Results

### Case Study 1: ASCT2 Inhibitors (14 molecules)
Testing showed SPARROW selected routes with cheaper starting materials and higher confidence reaction scores compared to baseline approaches that scored molecules individually without considering batch economics.

### Case Study 2: Autonomous Design Cycle (121 molecules)
SPARROW identified which molecules to synthesize and which to purchase directly, demonstrating how overlapping intermediates and reaction steps reduce overall batch costs. The algorithm also formalized the medicinal chemistry principle of "testing intermediates."

### Case Study 3: Alectinib Analogs (300 candidates)
The framework scaled to hundreds of molecules, selecting routes that shared starting materials and reaction steps.

**Execution Time (300 candidates, full workflow):**
- Total: ~13 hours
- Retrosynthesis planning: ~5 hours
- Compound cost lookup: ~4 hours
- Condition recommendation + scoring: ~4 hours

### Key Contributions

1. **Captures non-additive batch synthesis costs:** Recognizes that adding a new structure's cost depends on molecules already chosen
2. **Leverages common reaction steps and intermediates:** Identifies shared synthetic pathways across molecule batches
3. **Scales to hundreds of molecules:** Practical for real-world pharmaceutical research
4. **Open-source implementation:** Freely available for community use and extension
5. **Integrates with existing tools:** Works with ASKCOS for retrosynthesis and ChemSpace for pricing
6. **Flexible weighting parameters:** Allows users to balance utility vs. cost based on project needs

---

## Limitations

### Explicitly Acknowledged Limitations

1. **Independent Rewards Assumption:** Treats molecular utilities as independent; does not consider marginal information gain related to molecular diversity

2. **Constant and Independent Reaction Costs:** Assumes reaction costs remain constant regardless of other selected reactions

3. **Excluded Costs:** Neglects costs related to solvents, reagents, and catalysts

4. **Linear Objective Function:** Uses a simplified linear formulation rather than the ideal nonlinear objective function for tractability

5. **No Diversity Optimization:** Current formulation does not explicitly optimize for structural diversity in selected batches

6. **No Parallel Chemistry Consideration:** Does not account for laboratory automation advantages or parallel synthesis benefits

### Lack of Enzymatic Reactions Support

**Critical Limitation:** The SPARROW framework contains **no treatment of enzymatic reactions or biocatalytic processes**. The paper and codebase are focused exclusively on traditional chemical synthesis approaches.

This is a significant gap because:
- Enzymatic conversions often provide superior regio- and stereoselectivity compared to chemical reactions
- Biocatalytic processes increasingly replace conventional organic synthesis steps due to mild solvents, metal-free conditions, and reduced non-biodegradable waste
- Chemo-enzymatic pathways combining both approaches can identify efficient routes beyond either modality alone

Related work by the Coley group on enzymatic retrosynthesis (e.g., "Similarity based enzymatic retrosynthesis," Chemical Science 2022) exists separately but is not integrated into SPARROW.

### Other Limitations

7. **API Dependencies:** Requires access to ASKCOS deployment and ChemSpace API for full functionality
8. **Computational Time:** Full workflow for large candidate sets can take many hours
9. **Reaction Template Coverage:** Limited by the reaction templates available in ASKCOS

---

## Future Directions (Stated by Authors)

- Relax assumptions related to synthetic cost
- Employ the original nonlinear objective function
- Incorporate diversity optimization and matched molecular pairs
- Expand to large candidate libraries
- Leverage improvements in property prediction and uncertainty quantification
- Include elements of parallel chemistry in cost-versus-value function
- Consider that the value of testing one compound may not always be constant

---

## Code Repositories and Implementation

### Primary Repository
**GitHub:** https://github.com/coleygroup/sparrow

**Repository Statistics:**
- 62 stars, 7 forks, 374 commits
- Languages: Jupyter Notebook (81.7%), Python (18.3%)
- License: MIT

### Installation Requirements

**Python Environment:**
- Python >= 3.7 (tested on 3.12)
- Dependencies listed in `requirements.txt`
- Conda/Mamba for environment management

**External Dependencies (optional):**
- ASKCOS API deployment (for retrosynthesis and scoring)
- ChemSpace API key (for compound cost/buyability)
- Gurobi license (alternative to PuLP for optimization)
- NameRxn executable (for reaction classification)

### Installation Steps
```bash
mamba env create -f environment.yml
conda activate sparrow
pip install -r requirements.txt
python setup.py develop
```

### Basic Usage
```bash
sparrow --target-csv <path> --path-finder {api,lookup} --recommender {api,lookup} --coster {naive,chemspace}
```

### Key Parameters

**Weighting Factors (linear formulation):**
- `--reward-weight` (default: 1)
- `--start-cost-weight` (default: 1)
- `--reaction-weight` (default: 1)

**Constraints:**
- `--max-targets`: candidate count limit
- `--max-rxns`: reaction step limit
- `--starting-material-budget`: cost ceiling
- `--N-per-cluster`: diversity enforcement

### Output Files
- `params.ini`: run parameters
- `summary.json`: selection statistics
- `routes.json`: synthetic routes per molecule
- `solution_list_format.json`: selected molecules, reactions, buyable materials

### Reusability Feature
Previously generated route graphs (`trees_w_info.json`) can be reused across runs with different weighting factors, avoiding expensive retrosynthesis recalculation.

### Related Tools
- **ASKCOS:** https://askcos.mit.edu/ - Retrosynthesis planning tool
- **ChemSpace:** Commercial compound database for pricing/availability

---

## References and Sources

### Primary Publication
- Fromer, J.C., Coley, C.W. An algorithmic framework for synthetic cost-aware decision making in molecular design. *Nat Comput Sci* **4**, 440-450 (2024). https://doi.org/10.1038/s43588-024-00639-y

### arXiv Preprint
- https://arxiv.org/abs/2311.02187

### Code Repository
- https://github.com/coleygroup/sparrow

### News Articles
- MIT News: https://news.mit.edu/2024/smarter-way-streamline-drug-discovery-0617
- MIT Schwarzman College of Computing: https://computing.mit.edu/news/a-smarter-way-to-streamline-drug-discovery/
- SciTechDaily: https://scitechdaily.com/mits-sparrow-redefines-drug-discovery-with-smart-synthesis/

### PubMed
- https://pubmed.ncbi.nlm.nih.gov/38886590/

---

## Summary

SPARROW represents a significant advance in computational approaches to molecular design by formalizing the expert chemist's intuition about batch synthesis economics. By integrating retrosynthesis planning (via ASKCOS), commercial pricing (via ChemSpace), and optimization (via MILP), it provides a principled framework for selecting which molecules to synthesize when exploring chemical space.

The main limitation relevant to expanding beyond traditional chemical synthesis is the complete absence of enzymatic reaction support. For projects considering biocatalytic or chemo-enzymatic routes, SPARROW would need substantial extension to incorporate enzyme databases, biocatalyst availability/cost, and enzymatic reaction prediction models.

The open-source nature of the code and its modular design make it amenable to community extensions addressing these and other limitations.

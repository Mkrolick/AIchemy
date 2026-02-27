# Direct Optimization across Computer-Generated Reaction Networks Balances Materials Use and Feasibility of Synthesis Plans for Molecule Libraries

## Full Citation

**Gao, H.; Pauphilet, J.; Struble, T. J.; Coley, C. W.; Jensen, K. F.** "Direct Optimization across Computer-Generated Reaction Networks Balances Materials Use and Feasibility of Synthesis Plans for Molecule Libraries." *Journal of Chemical Information and Modeling* **2021**, *61*(1), 493-504.

- **DOI:** [10.1021/acs.jcim.0c01032](https://pubs.acs.org/doi/10.1021/acs.jcim.0c01032)
- **PMID:** 33331158
- **Published Online:** December 17, 2020
- **Print Issue:** January 25, 2021

### Author Affiliations

| Author | Affiliation |
|--------|-------------|
| Hanyu Gao | Department of Chemical Engineering, Massachusetts Institute of Technology |
| Jean Pauphilet | London Business School |
| Thomas J. Struble | Department of Chemical Engineering, Massachusetts Institute of Technology |
| Connor W. Coley | Department of Chemical Engineering, Massachusetts Institute of Technology |
| Klavs F. Jensen | Department of Chemical Engineering, Massachusetts Institute of Technology |

---

## Abstract/Overview

The synthesis of thousands of candidate compounds in drug discovery and development offers opportunities for computer-aided synthesis planning to simplify the synthesis of molecule libraries by leveraging common starting materials and reaction conditions. The authors develop an optimization-based method to analyze large organic chemical reaction networks and design overlapping synthesis plans for entire molecule libraries so as to minimize the overall number of unique chemical compounds needed as either starting materials or reaction conditions.

The method considers multiple objectives, including:
1. The number of starting materials
2. The number of catalysts/solvents/reagents
3. The likelihood of success of the overall synthesis plan

These objectives are balanced to select an optimal reaction network to access the target molecules. The library synthesis planning task was formulated as a **network flow optimization problem**, and the authors design an efficient **decomposition scheme** that reduces solution time by a factor of 5 and scales to instances with 48 target molecules and nearly 8000 intermediate reactions within hours.

---

## Key Methodology

### Relationship to the 2020 Precursor Work

This paper is a direct follow-up to the authors' 2020 publication:

> **Gao, H.; Coley, C. W.; Struble, T. J.; Li, L.; Qian, Y.; Green, W. H.; Jensen, K. F.** "Combining Retrosynthesis and Mixed-Integer Optimization for Minimizing the Chemical Inventory Needed to Realize a WHO Essential Medicines List." *Reaction Chemistry & Engineering* **2020**, *5*, 367-376. [DOI: 10.1039/C9RE00348G](https://pubs.rsc.org/en/content/articlelanding/2020/re/c9re00348g)

The 2020 paper introduced the concept of combining ML-based retrosynthesis with mixed-integer programming (MIP) to minimize chemical inventory for synthesizing WHO essential medicines. The 2021 JCIM paper extends this work by:

1. **Generalizing the optimization framework** from essential medicines to arbitrary molecule libraries in drug discovery
2. **Introducing a network flow formulation** that more naturally captures the synthesis planning problem
3. **Developing an efficient decomposition scheme** that dramatically improves computational scalability
4. **Explicitly balancing multiple objectives** including feasibility/confidence of synthesis routes

### Core Methodology Components

#### 1. Retrosynthetic Network Generation
- Utilizes **ASKCOS** (a software package for computer-aided synthesis planning developed at MIT) to generate retrosynthetic routes for target molecules
- Creates a large reaction network containing all possible synthesis pathways connecting target molecules to commercially available starting materials
- Networks can contain thousands of intermediate reactions

#### 2. Network Flow Optimization Formulation
The library synthesis planning task is formulated as a **network flow optimization problem** where:
- Nodes represent chemical compounds (targets, intermediates, starting materials)
- Edges represent chemical reactions
- Flow through the network represents material requirements
- The objective minimizes total unique compounds (starting materials + reagents) while maximizing synthesis feasibility

#### 3. Multi-Objective Optimization
The optimization considers a weighted combination of:
- **Minimizing starting materials:** Reducing the number of unique precursor compounds
- **Minimizing catalysts/solvents/reagents:** Reducing auxiliary chemicals needed
- **Maximizing synthesis feasibility:** Selecting routes with higher predicted success probabilities

Users can adjust weights to explore the Pareto trade-off between material efficiency and synthesis reliability.

#### 4. Decomposition Scheme
A key technical contribution is the **efficient decomposition scheme** that:
- Breaks the large MILP problem into smaller, tractable subproblems
- Reduces solution time by a factor of 5 compared to solving the monolithic problem
- Enables scaling to instances with 48 target molecules and ~8000 intermediate reactions
- Solutions can be obtained within hours on standard hardware

### Pipeline Workflow

1. **Input:** Target molecule SMILES strings for the library
2. **Step 1 - Retrosynthesis:** Generate reaction networks using ASKCOS
3. **Step 2 - Condition Prediction:** Evaluate reaction conditions and feasibility scores
4. **Step 3 - Optimization:** Solve the network flow MILP with user-specified objective weights
5. **Output:** Optimal synthesis plans with minimized material requirements

---

## Main Results and Contributions

### Quantitative Results

The approach was validated on **four case studies of pharmaceutical compounds**:

| Metric | Average Reduction | Best Case Reduction |
|--------|-------------------|---------------------|
| Starting Materials | **32.2%** | **63.2%** |
| Catalysts/Solvents/Reagents | **66.0%** | **80.0%** |

### Scalability Demonstration

- Successfully handled instances with **48 target molecules**
- Processed networks with **nearly 8000 intermediate reactions**
- Solutions obtained **within hours** using the decomposition scheme
- **5x speedup** compared to solving without decomposition

### Key Contributions

1. **Network Flow Formulation:** Novel formulation of library synthesis planning as a network flow optimization problem, enabling efficient mathematical treatment

2. **Scalable Decomposition:** Development of a decomposition scheme that makes the approach practical for realistically-sized molecule libraries

3. **Multi-Objective Framework:** Explicit handling of trade-offs between material efficiency and synthesis feasibility through weighted objectives

4. **Integration with ML-based Retrosynthesis:** Seamless connection with ASKCOS for automated generation of synthesis networks

5. **Practical Utility:** Demonstrated significant material savings (up to 63% starting materials, 80% reagents) on pharmaceutical case studies

---

## Limitations

### Computational Limitations

1. **Scalability Ceiling:** While the decomposition scheme provides significant improvements, the approach still faces exponential growth in computational complexity for very large molecule libraries (>50 targets) or highly complex reaction networks

2. **Exact Optimality:** Finding exact optimal pathways becomes increasingly challenging as network size grows; the approach may find approximate solutions for larger instances

3. **Solver Dependency:** Requires commercial GUROBI optimizer for the MILP solving, which may limit accessibility for some users

### Methodology Limitations

1. **Retrosynthesis Quality Dependency:** The optimization is only as good as the underlying retrosynthetic predictions from ASKCOS; errors in reaction prediction propagate through the optimization

2. **Reaction Condition Simplification:** Grouping of catalysts/solvents/reagents may oversimplify the actual requirements for reaction execution

3. **Linear Objective Combination:** The weighted sum approach to multi-objective optimization can miss Pareto-optimal solutions in non-convex regions of the trade-off surface

4. **Static Network Analysis:** The approach optimizes over a pre-computed reaction network; it does not adaptively explore new synthesis routes during optimization

### Practical Limitations

1. **No Experimental Validation:** The paper presents computational case studies but does not include experimental synthesis of the proposed routes

2. **Supply Chain Dynamics:** Does not consider real-world factors like chemical availability, pricing, or delivery times

3. **Stereochemistry Handling:** Limited treatment of stereochemical considerations in synthesis planning

---

## Code Repositories

### Primary Repository

**GitHub:** [https://github.com/Coughy1991/Molecule_library_synthesis](https://github.com/Coughy1991/Molecule_library_synthesis)

**Description:** Optimizing synthesis plan for molecule libraries with focus on minimizing material use

**Requirements:**
- Python environment (conda recommended via `environment.yml`)
- ASKCOS software (clone from https://github.com/Coughy1991/ASKCOS)
- GUROBI optimizer (free academic licenses available at https://www.gurobi.com/)

**Usage:**
```bash
# Step 1: Retrosynthesis
KERAS_BACKEND=theano python tree_builder_for_multiple_targets.py case_1

# Evaluate reactions
KERAS_BACKEND=theano python predict_conditions_and_evaluate.py case_1

# Step 2: Optimization
python optimize_synthesis_plan_for_library.py -directory case_1 -decomposition -weights 10 1 0.1
```

### Related Repositories

- **ASKCOS Main Repository:** [https://github.com/ASKCOS/ASKCOS](https://github.com/ASKCOS/ASKCOS)
  - Software package for computer-aided synthesis planning
  - Provides retrosynthetic analysis, reaction prediction, and condition recommendation
  - Released under MPL 2.0 license (models under CC BY-NC-SA for non-commercial use)

### Fork

- **Fork:** [https://github.com/sailfish009/Molecule_library_synthesis](https://github.com/sailfish009/Molecule_library_synthesis)

---

## Related Publications

### Precursor Work (2020)

> **Gao, H.; Coley, C. W.; Struble, T. J.; Li, L.; Qian, Y.; Green, W. H.; Jensen, K. F.** "Combining Retrosynthesis and Mixed-Integer Optimization for Minimizing the Chemical Inventory Needed to Realize a WHO Essential Medicines List." *React. Chem. Eng.* **2020**, *5*, 367-376. [DOI: 10.1039/C9RE00348G](https://pubs.rsc.org/en/content/articlelanding/2020/re/c9re00348g)

- Introduced the concept of combining ML-based retrosynthesis with MIP optimization
- Focused specifically on WHO essential medicines list
- Demonstrated technical feasibility of reducing API storage to minimal starting material inventory

### Follow-up Work

> **Fromer, J. C.; Coley, C. W.** "An Algorithmic Framework for Synthetic Cost-aware Decision Making in Molecular Design." *Nature Computational Science* **2024**. [Link](https://www.nature.com/articles/s43588-024-00639-y)

- Extends synthesis-aware optimization to molecular design
- Integrates synthesis cost considerations directly into generative molecular design

---

## Supporting Information

The paper includes supplementary materials available at the ACS website:

- **ci0c01032_si_001.pdf** (14.32 MB): Comparison of computational time, full pathways for Cases 1-4
- **ci0c01032_si_002.xlsx** (11.09 KB): SMILES strings for molecules used in case studies

---

## Summary

This 2021 JCIM paper by Gao et al. represents an important advancement in computer-aided synthesis planning for molecule libraries. By formulating library synthesis as a network flow optimization problem and introducing an efficient decomposition scheme, the authors demonstrate that significant material savings (30-60% for starting materials, 60-80% for reagents) can be achieved when planning synthesis across multiple targets simultaneously. The work bridges machine learning-based retrosynthesis (via ASKCOS) with rigorous mathematical optimization (MILP), providing a practical framework for pharmaceutical development where large numbers of candidate compounds must be synthesized efficiently. While limitations remain in scalability and reliance on computational predictions without experimental validation, the framework establishes a foundation for optimization-driven approaches to multi-target synthesis planning.

---

*Report generated: 2026-02-26*

*Sources: [PubMed](https://pubmed.ncbi.nlm.nih.gov/33331158/), [ACS Publications](https://pubs.acs.org/doi/10.1021/acs.jcim.0c01032), [Jensen Lab Publications](https://jensenlab.mit.edu/publications-recent/), [Coley Lab Publications](https://coley.mit.edu/publications), [Hanyu Gao Research Group](https://hanyugao.com/publications/)*

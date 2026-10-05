# Multi-Objective MILP for Retrosynthesis: WHO Essential Medicines

## Full Citation

**Gao, H., Coley, C. W., Struble, T. J., Li, L., Qian, Y., Green, W. H., & Jensen, K. F.** (2020). Combining retrosynthesis and mixed-integer optimization for minimizing the chemical inventory needed to realize a WHO essential medicines list. *Reaction Chemistry & Engineering*, 5(2), 367-376.

**DOI:** [10.1039/C9RE00348G](https://doi.org/10.1039/C9RE00348G)

**Published:** January 2, 2020 (Received: August 23, 2019; Accepted: January 2, 2020)

**Access:** Open Access (Creative Commons Attribution 3.0 License)

### Author Affiliations

| Author | Affiliation |
|--------|-------------|
| Hanyu Gao | MIT Department of Chemical Engineering |
| Connor W. Coley | MIT Department of Chemical Engineering |
| Thomas J. Struble | MIT Department of Chemical Engineering |
| Linyan Li | Harvard T.H. Chan School of Public Health |
| Yujie Qian | MIT Computer Science & Artificial Intelligence Laboratory |
| William H. Green | MIT Department of Chemical Engineering |
| Klavs F. Jensen (Corresponding) | MIT Department of Chemical Engineering |

---

## Abstract / Overview

Access to essential medicines remains a significant challenge in low-income countries due to logistical constraints, expiration limits, and supply chain difficulties. This paper proposes a solution through on-demand manufacturing from stored starting materials, enabling flexible replenishment and easier supply chain management.

The researchers developed a computational framework that:
1. Uses machine learning-based retrosynthetic analysis to generate candidate synthetic routes
2. Solves a multi-objective mixed-integer programming (MILP) problem to select optimal pathway combinations
3. Minimizes the total chemical inventory while maximizing the perceived chemical feasibility of pathways

The analysis targets molecules from the World Health Organization (WHO) essential medicines list, demonstrating that combined pathway selection can reduce the required chemical inventory by approximately 25% compared to selecting pathways independently.

---

## Key Methodology

### Retrosynthesis Platform

The study leverages the **ASKCOS** (Automated Synthesis Planning via Computer-Aided Search for Knowledge in Organic Synthesis) platform, which includes:

- **Tree Builder**: Automated retrosynthetic planning using Monte Carlo Tree Search (MCTS) and Retro* algorithms
- **Condition Recommender**: Predicts reaction conditions (solvents, catalysts, reagents)
- **Reaction Evaluator**: Assesses forward reaction feasibility

**Search Parameters:**
- Maximum tree depth: 10 steps
- Search time limit: 100 seconds per target
- Maximum pathways: 10,000 per target (capped)

### Multi-Objective MILP Formulation

The optimization problem balances two competing objectives:

**Objective 1: Minimize Total Chemicals Used**
- Weighted by synthetic complexity scores
- Tracks both starting materials and reaction auxiliaries (solvents, catalysts, reagents)

**Objective 2: Maximize Pathway Feasibility**
- Based on cumulative reaction success probabilities
- Uses ML-predicted forward reaction scores

#### Mathematical Formulation

**Decision Variables:**
- `x_ij` (binary): Whether pathway j for target i is selected
- `y_k` (binary): Whether chemical k is included in the inventory

**Constraints:**
- Exactly one pathway must be selected per target
- Chemical usage tracked across all selected routes

**Combined Objective Function:**

```
minimize: lambda * (sum of y_k) - (1 - lambda) * (sum of pathway scores * x_ij)
```

### Lambda-Weight Variation for Pareto Front

The weight parameter lambda systematically varies from 0 to 1 to generate the complete Pareto frontier:

| Lambda Value | Objective Focus | Starting Materials | Average Score |
|--------------|-----------------|-------------------|---------------|
| lambda = 0 | Maximize pathway quality | 236 | 0.663 |
| lambda = 0.5 | Balanced optimization | 187 | 0.566 |
| lambda = 1 | Minimize chemicals | 175 | 0.230 |

This analysis revealed that substantial chemical reduction (approximately 25%) can be achieved with minimal feasibility compromises.

### CPLEX Solver Implementation

The optimization was implemented using:
- **IBM ILOG CPLEX** with Python API
- Linear problem formulation ensures guaranteed global optimality
- Deterministic solutions across all lambda values
- No initial guess required due to linear formulation

---

## Main Results and Contributions

### Retrosynthesis Analysis Results

**Initial Analysis (127 targets from WHO list):**
- Successfully generated pathways for **112 of 127 targets** (88.2% success rate)
- Total unique pathways found: **492,860** (capped at 10,000 per target)
- After quality filtering: **193,597 pathways** for **99 targets**
- Chemical inventory: 3,340 starting materials + 570 reaction auxiliaries

### Optimization Results

**Separate Analysis (lambda = 0):**
Selecting highest-scoring pathways individually:
- 236 starting materials
- 135 auxiliaries (solvents/catalysts/reagents)
- Total: 371 chemicals

**Combined Analysis (lambda = 0.5):**
Optimized pathway selection:
- 187 starting materials (approximately 21% reduction)
- 99 auxiliaries (approximately 27% reduction)
- Total: 286 chemicals (approximately 25% reduction)

### Key Insights

1. **Shared chemicals concentrate among multiple targets** rather than improving direct pairwise similarity
2. **Example shared chemicals:**
   - 1-bromo-4-chlorobenzene: shared by 3 targets
   - Methanol: used across 10 targets
3. **Stricter quality filtering** (excluding pathways with reaction scores < 0.05):
   - 54,204 pathways for 78 targets
   - 17% reduction still achievable (250 vs. 301 chemicals)

### Computational Requirements

- **Hardware:** Dual Intel Xeon processors, 128GB RAM
- **Total computation time:** 75 hours for 127 targets
- **Includes:** Retrosynthesis analysis, condition recommendation, and forward evaluation

### Primary Contributions

1. **First demonstration** of combining ML-based retrosynthesis with MILP for multi-target synthesis optimization
2. **Quantitative evidence** that coordinated pathway selection reduces chemical inventory by approximately 25%
3. **Framework** applicable to any set of target molecules, not just essential medicines
4. **Open-source implementation** enabling reproducibility and extension

---

## Limitations

### Methodological Scope Limitations

1. **Inventory Count vs. Monetary Cost:**
   - The optimization minimizes the *number* of distinct chemicals, not monetary cost
   - Does not incorporate chemical pricing data
   - Does not account for demand volumes or bulk purchasing considerations

2. **No Enzymatic Reactions:**
   - The retrosynthesis platform focuses exclusively on traditional organic synthesis
   - Biocatalytic transformations are not included in the reaction database
   - Excludes chemo-enzymatic hybrid routes that may be more efficient for certain targets

3. **Single Condition Selection:**
   - Only one set of reaction conditions selected per reaction step
   - Limits potential for solvent/reagent consolidation across reactions
   - May miss opportunities for standardized reaction protocols

4. **Search Constraints:**
   - Tree depth capped at 10 steps
   - Search time limited to 100 seconds per target
   - May miss longer but more practical routes

### Model-Related Limitations

1. **Missing Reaction Conditions:**
   - Common solvents (particularly water) frequently omitted from condition recommendations
   - Database entry gaps affect prediction quality

2. **Selectivity Ambiguities:**
   - Reactivity/selectivity can only be confirmed via experiments
   - ML predictions may not capture subtle stereochemical or regiochemical issues

3. **False Negatives:**
   - Complex multi-step reactions recorded as single transformations may score below thresholds
   - Literature-validated reactions occasionally rejected by forward evaluation

4. **Missing Reagents:**
   - Some predicted reactions lack essential stoichiometric components
   - Alkylating agents or atom sources sometimes not predicted

5. **Structural Redundancies:**
   - Some pathways appear circular or unnecessarily complex
   - Tree retrieval procedures need improvement

### Practical Implementation Limitations

- Experimental validation not performed
- Process development considerations not addressed
- Regulatory and policy approval requirements beyond scope
- Does not account for equipment availability or manufacturing constraints

---

## Code Repositories and Data

### Primary Repository

**GitHub:** [https://github.com/Coughy1991/Combined_synthesis_planning](https://github.com/Coughy1991/Combined_synthesis_planning)

**Contents:**
- `tree_builder_with_evaluation_for_multiple_targets.py` - Retrosynthetic pathway planning
- `optimization_of_pathway_selection.ipynb` - MILP optimization implementation
- `Analyze_results.ipynb` - Results analysis and visualization
- `tree_visualization_template.html` - Interactive tree visualization template

**Dependencies:**
- Python libraries: pandas, rdkit, pulp
- Optimization solver: CPLEX (or alternative solvers)
- Jupyter Notebook environment

### Pre-computed Data (Figshare)

- Unfiltered retrosynthetic trees for 99 WHO essential medicines
- Filtered trees (at most 1 low-score reaction per pathway)

### Related Software

**ASKCOS Platform:**
- GitHub: [https://github.com/ASKCOS/ASKCOS](https://github.com/ASKCOS/ASKCOS)
- Public instance: [https://askcos.mit.edu/](https://askcos.mit.edu/)

---

## Impact and Follow-up Work

This paper established a foundation for:
1. Multi-target synthesis planning optimization
2. Integration of ML-based retrosynthesis with operations research methods
3. Supply chain optimization for pharmaceutical manufacturing

The methodology has influenced subsequent work in:
- Synthetic route scoring and evaluation
- Cost-aware molecular design
- Automated synthesis planning systems

---

## References

1. Gao, H., Coley, C. W., Struble, T. J., Li, L., Qian, Y., Green, W. H., & Jensen, K. F. (2020). *Reaction Chemistry & Engineering*, 5(2), 367-376. DOI: 10.1039/C9RE00348G

2. ASKCOS Documentation and Software: https://askcos.mit.edu/

3. Jensen Research Group Publications: https://jensenlab.mit.edu/publications-recent/

4. Coley Lab Publications: https://coley.mit.edu/publications

---

*Report generated: February 2026*

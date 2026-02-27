# novoStoic 2.0: Integrated Framework for Pathway Synthesis, Thermodynamic Evaluation, and Enzyme Selection

## Citation

**Full Citation:**
Upadhyay V, Anand M, Maranas CD. novoStoic2.0: An integrated framework for pathway synthesis, thermodynamic evaluation, and enzyme selection. *PLoS Computational Biology*. 2025 Aug 6;21(8):e1012516.

**DOI:** [10.1371/journal.pcbi.1012516](https://doi.org/10.1371/journal.pcbi.1012516)

**Authors:**
- Vikas Upadhyay
- Mohit Anand
- Costas D. Maranas

**Affiliation:** Department of Chemical Engineering, The Pennsylvania State University, University Park, Pennsylvania, United States

**Funding:** National Science Foundation Molecule Maker Lab Institute (MMLI), Award 2019897

---

## Abstract / Overview

novoStoic2.0 is an integrated computational platform that combines tools for estimating overall stoichiometry, designing de novo synthesis pathways, assessing thermodynamic feasibility, and selecting enzymes for biosynthetic pathway design. The platform offers a unified web-based interface as part of the AlphaSynthesis platform, providing researchers with a comprehensive workflow for designing thermodynamically viable biosynthetic routes.

**Key Innovation:** Unlike existing pathway design tools that focus solely on pathway generation and require separate analyses for thermodynamics, enzyme selection, and reaction balance, novoStoic2.0 integrates all these aspects into a single unified framework. This integration enables the construction of biosynthetic routes that are thermodynamically viable (energetically favorable and chemically feasible) while identifying which steps may require enzyme re-engineering.

---

## Key Methodology

### 1. Overall Architecture

novoStoic2.0 integrates four core computational modules:

| Module | Function | Runtime |
|--------|----------|---------|
| **optStoic** | Overall stoichiometry optimization | ~1 minute |
| **novoStoic** | De novo pathway search | ~2.5 hours |
| **dGPredictor** | Thermodynamic feasibility assessment | ~2 minutes |
| **EnzRank** | Enzyme selection and ranking | ~1 minute |

### 2. optStoic: Stoichiometry Optimization

optStoic solves a **Linear Programming (LP) problem** that maximizes theoretical yield while enforcing:
- Mass balance
- Energy balance
- Charge balance
- Atom balance

The module accepts source and target molecules along with optional co-substrates/co-products (including cofactors like NAD(P)H, NAD(P)+) to determine optimal stoichiometry for a given biotransformation.

**Important Limitation:** Optimal stoichiometry does not guarantee a viable pathway design, since the LP maximizes yield without ensuring biochemical feasibility of individual reaction steps.

### 3. novoStoic: MILP-Based De Novo Pathway Design

The novoStoic algorithm uses a **Mixed-Integer Linear Programming (MILP)** representation to identify component and moiety balanced biochemical pathways converting a source to a target metabolite.

#### Database Processing
- **Input:** 74,612 reactions and 1,292,153 molecules from MetaNetX database
- **Processing:** Removal of unbalanced reactions, transport reactions, and reactions containing generic molecules
- **Output:** 23,585 reactions and 17,154 molecules retained for pathway design
- **Reaction Rules:** 9,686 unique reaction rules generated from processed reactions

#### MILP Formulation Components

**Objective Functions:**
- Maximization of profit margin (cost difference between substrate and product)
- Minimization of number of novel reaction steps
- Minimization of total pathway length

**Key Constraints:**

1. **Component Balance:** Maintains mass balance across all metabolites in the network

2. **Moiety Balance:** The overall change for moiety *m* across exchange reactions equals the moiety changes in both novel and known reaction networks

3. **Linked Balances:** Component and moiety balances are linked through the imbalance metabolic flux (v_imb), which quantifies surplus or deficit for metabolites requiring novel reaction steps

#### rePrime Encoding

The rePrime technique uses **prime factorization-based encoding** to track and codify reaction centers:

- **Molecular Signature (C_mi^λ):** A vector concatenating the number of attributes for every moiety *m* in metabolite *i*
- **Moiety Size (λ):**
  - λ = 1: Single atom at node n
  - λ = 2: All atoms bonded to the atom at node n
  - λ = 3: Extended neighborhood (current implementation maximum)
- **Reaction Rules (T_mr^λ):** Capture changes in all moieties of participating metabolites

### 4. dGPredictor: Thermodynamic Feasibility Assessment

dGPredictor estimates the **standard Gibbs energy change (ΔrG'°)** for reactions using automated chemical moieties rather than expert-defined functional groups.

**Methodology:**
- Uses automated moiety-based molecular fragmentation based on neighboring bonds and atoms
- SMILES-based moiety definitions allow stereochemical consideration
- Multi-linear regression (Bayesian ridge regression) estimates individual group contributions
- 1,643 moieties with well-determined ΔgG° contributions

**Key Features:**
- Handles novel metabolites absent from databases through InChI string inputs
- Supports pH and ionic strength adjustments
- Achieves ~100% reaction coverage with Bayesian regression
- Captures Gibbs energy changes for isomerase and transferase reactions (which exhibit no overall group changes)

**Integration:** Safeguards against using reactions or novel conversion steps in thermodynamically unfavorable directions.

### 5. EnzRank: CNN-Based Enzyme Selection

EnzRank uses **Convolutional Neural Networks (CNNs)** to rank-order known enzymes for their suitability as starting points for protein engineering toward novel substrate activity.

#### CNN Architecture

**Input Streams:**
- **Enzyme sequences:** Processed through convolutional layers with configurable window sizes (10, 15, 20, 25, 30)
- **Substrate structures:** Morgan fingerprints (radius 2, 2048 bits)

**Network Design:**
- Parallel convolutional pathways for enzyme sequence features
- Dense layers for substrate processing
- Concatenated feature layers for final classification
- ELU activation function
- Configurable filters per layer (default: 128)

**Training Parameters:**
- Learning rate: 0.0001
- Batch size: 32
- Dropout: 0.0

#### Training Data

- **Source:** 11,800 known active enzyme-substrate pairs from BRENDA database (positive samples)
- **Negative Sample Generation:** Scrambled pairs using substrate dissimilarity (Tanimoto similarity score) between an enzyme's native substrate and all other molecules
- **Validation:** 10-fold holdout method for training and cross-validation

#### Performance Metrics

| Metric | Value |
|--------|-------|
| Positive pair recovery rate | 80.72% |
| Negative pair recovery rate | 73.08% |
| Evaluation metrics | AUC, AUPR |

**Databases Queried:** KEGG, Rhea (3,744 unique enzyme sequences in case study)

---

## Main Results and Contributions

### 1. Hydroxytyrosol Case Study

The platform's capabilities were demonstrated by designing biosynthetic pathways for hydroxytyrosol, a compound with industrial and biomedical relevance as an antioxidant.

**Pathway 1:** Four-step route from L-tyrosine
- Follows known literature strategy
- Requires cofactors (NAD(P)H usage)

**Pathway 2:** Three-step cofactor-free alternative
- Novel route requiring only small molecule co-reactants/products
- **Shorter than established methods**
- **Reduced cofactor requirements**

### 2. Tool Comparison

novoStoic2.0 was compared against existing tools:
- RetroBioCat
- RetroPath2.0
- BioNavi
- PathPred
- XTMS
- enviPath

**Unique Advantages of novoStoic2.0:**
1. Integration of thermodynamic feasibility checks
2. Enzyme candidate ranking for pathway steps
3. Balanced stoichiometry including cofactors
4. Unified single framework (competitors require separate analyses)

### 3. Key Contributions

1. **Unified Platform:** First integrated workflow combining stoichiometry optimization, pathway design, thermodynamic assessment, and enzyme selection

2. **Thermodynamic Safeguards:** Prevents design of thermodynamically infeasible pathways

3. **Novel Step Identification:** Identifies which steps require enzyme re-engineering and provides enzyme candidates

4. **Cofactor Management:** Explicit handling of cofactor regeneration and balance

5. **Web-Based Interface:** Accessible platform as part of AlphaSynthesis ecosystem

---

## Limitations

### 1. Enzymatic Reactions Only
- The platform is designed exclusively for **enzymatic biotransformations**
- Does not support **chemical synthesis** steps or hybrid chemo-enzymatic routes
- Cannot incorporate abiotic catalysis or non-enzymatic transformations

### 2. No Pricing or Economic Data
- No integration of **chemical pricing** or cost databases
- Cannot optimize pathways based on economic feasibility or substrate costs
- Profit margin optimization requires manual input of cost data

### 3. Computational Constraints
- Web platform limited to **two runs** due to computational constraints
- Pathway searches support up to **10 distinct pathways**, each with up to **10 reactions**
- dGPredictor evaluates up to **5 reactions simultaneously**
- Pathway searches generally require **several hours** to complete (~2.5 hours typical)

### 4. Database Dependencies
- Relies on MetaNetX database reactions (23,585 curated reactions)
- Novel reactions limited to 9,686 reaction rules
- Enzyme selection limited to enzymes in KEGG and Rhea databases

### 5. Stoichiometry vs. Pathway Viability
- Optimal stoichiometry (from optStoic) does not guarantee a viable pathway design
- LP maximizes yield without ensuring biochemical feasibility of individual steps

### 6. Negative Sample Generation Methodology
- EnzRank uses artificially scrambled pairs as negative training data
- May not fully capture real-world enzyme-substrate incompatibility patterns

---

## Code and Data Availability

### GitHub Repositories

| Repository | URL |
|------------|-----|
| **novoStoic2.0** | [github.com/maranasgroup/novoStoic2.0](https://github.com/maranasgroup/novoStoic2.0) |
| **EnzRank** | [github.com/maranasgroup/EnzRank](https://github.com/maranasgroup/EnzRank) |
| **dGPredictor** | [github.com/maranasgroup/dGPredictor](https://github.com/maranasgroup/dGPredictor) |
| **rePrime_novoStoic (v1)** | [github.com/maranasgroup/rePrime_novoStoic](https://github.com/maranasgroup/rePrime_novoStoic) |

### Web Platforms

| Platform | URL |
|----------|-----|
| **novoStoic2.0 Web Interface** | [novostoic.platform.moleculemaker.org](https://novostoic.platform.moleculemaker.org/) |
| **EnzRank Web Interface** | [huggingface.co/spaces/vuu10/EnzRank](https://huggingface.co/spaces/vuu10/EnzRank) |

### Data Repository

**ScholarSphere:** [doi.org/10.26207/fxd2-se27](https://doi.org/10.26207/fxd2-se27)

### Dependencies (from GitHub)

- RDKit
- TensorFlow 2
- Streamlit
- Pandas, NumPy
- Keras
- scikit-learn
- matplotlib
- PuLP
- CPLEX solver
- ChemAxon's Marvin (≥5.11)
- Open Babel

---

## Related Publications

1. **Original novoStoic (v1):**
   Kumar A, Wang L, Ng CY, Maranas CD. Pathway design using de novo steps through uncharted biochemical spaces. *Nature Communications*. 2018;9:184. [DOI: 10.1038/s41467-017-02362-x](https://doi.org/10.1038/s41467-017-02362-x)

2. **EnzRank:**
   Upadhyay V, Boorla VS, Maranas CD. Rank-ordering of known enzymes as starting points for re-engineering novel substrate activity using a convolutional neural network. *Metabolic Engineering*. 2023;78:171-182. [DOI: 10.1016/j.ymben.2023.06.001](https://doi.org/10.1016/j.ymben.2023.06.001)

3. **dGPredictor:**
   Wang L, Upadhyay V, Maranas CD. dGPredictor: Automated fragmentation method for metabolic reaction free energy prediction and de novo pathway design. *PLoS Computational Biology*. 2021;17(9):e1009448. [DOI: 10.1371/journal.pcbi.1009448](https://doi.org/10.1371/journal.pcbi.1009448)

---

## Relevance to AIchemy

novoStoic2.0 represents a state-of-the-art approach for **enzymatic biosynthetic pathway design** that could inform or complement chemoinformatic retrosynthesis approaches:

**Potential Integration Points:**
- EnzRank's enzyme-substrate compatibility scoring could be adapted for enzyme selection in hybrid chemo-enzymatic routes
- dGPredictor's thermodynamic assessment methodology could complement chemical reaction feasibility evaluation
- MILP-based pathway optimization framework could inspire similar approaches for chemical synthesis planning

**Gaps Relative to AIchemy Goals:**
- No chemical synthesis capability (enzymatic only)
- No integration with chemical pricing databases
- No consideration of reagent availability or commercial sourcing
- Limited to biotransformations rather than comprehensive retrosynthesis

---

*Report generated: 2025-02-26*
*Source: PLoS Computational Biology, August 2025*

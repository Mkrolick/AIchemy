# ChemEnzyRetroPlanner: A Virtual Platform for Automated Hybrid Organic-Enzymatic Synthesis Planning

## Research Report

**Date:** February 2026
**Report Type:** Literature Review and Technical Analysis

---

## Full Citation

**Title:** A virtual platform for automated hybrid organic-enzymatic synthesis planning

**Authors:** Xiaorui Wang, Xiaodan Yin, Xujun Zhang, Huifeng Zhao, Shukai Gu, Zhenxing Wu, Odin Zhang, Wenjia Qian, Yuansheng Huang, Yuquan Li, Dejun Jiang, Mingyang Wang, Huanxiang Liu, Xiaojun Yao, Chang-Yu Hsieh, and Tingjun Hou

**Journal:** Nature Communications

**Publication Date:** November 26, 2025

**DOI:** [10.1038/s41467-025-65898-3](https://doi.org/10.1038/s41467-025-65898-3)

**Bibcode:** 2025NatCo..1610929W

---

## Abstract / Overview

The integration of organic synthesis with enzymatic catalysis offers a promising route toward efficient and sustainable construction of complex molecules. While organic synthesis enables diverse transformations, enzymatic catalysis enhances stereoselectivity under mild conditions, improving cost-effectiveness and environmental impact. However, current enzymatic synthesis planning algorithms face challenges in formulating robust hybrid organic-enzymatic strategies. Key issues include the difficulty in devising hybrid planning approaches and the reliance on template-based enzyme recommendations, which limits their adaptability across diverse scenarios.

ChemEnzyRetroPlanner addresses these challenges as an open-source hybrid synthesis planning platform that combines organic and enzymatic strategies with AI-driven decision-making. The platform features advanced computational modules, including hybrid retrosynthesis planning, reaction condition prediction, plausibility evaluation, enzymatic reaction identification, enzyme recommendation, and in silico validation of enzyme active sites. A central innovation is the **Retro-Rollout*** search algorithm, which outperforms existing tools in planning synthesis routes for organic compounds and natural products across multiple datasets.

ChemEnzyRetroPlanner provides an intuitive graphical interface and programmatic APIs for scalability, while leveraging the chain-of-thought strategy and the Llama3.1 model to autonomously activate hybrid synthesis strategies for diverse scenarios.

---

## Key Methodology

### 1. Neural Network-Guided Tree Search: Retro-Rollout* Algorithm

The Retro-Rollout* algorithm is a central innovation in ChemEnzyRetroPlanner that enhances retrosynthetic planning efficiency.

**Algorithm Design:**
- The "Selection" and "Update" steps remain consistent with the original Retro* algorithm
- A **jump search strategy** targeting sibling nodes of successful nodes is introduced during the Rollout step to enhance search efficiency
- When one of a pair of sibling nodes is confirmed to be successful (i.e., purchasable or synthesizable), that node is prioritized for expansion

**Guiding Function:**
- Replaced with a **synthesis route depth-based guiding function**
- Estimates the number of steps from the molecular node to the purchasable dataset
- Implemented using a **multilayer perceptron (MLP) classification model** based on molecular fingerprints

### 2. Seven Computational Modules

ChemEnzyRetroPlanner offers seven key computational modules:

| Module | Description |
|--------|-------------|
| **Multi-step Synthesis Planner** | Plans complete synthesis routes using Retro-Rollout* |
| **Single-step Retrosynthesis Predictor** | Template-based and template-free reaction prediction |
| **Reaction Condition Predictor** | Predicts catalysts, solvents, reagents, and temperature |
| **Reaction Rate Predictor** | Estimates reaction kinetics |
| **Enzymatic Reaction Identifier** | Identifies enzymatic transformation opportunities |
| **Enzyme Recommender** | Suggests appropriate enzymes for reactions |
| **Enzyme Active Site Annotator (EasIFA)** | In silico validation of enzyme active sites |

### 3. Single-Step Retrosynthesis Models

The platform integrates multiple single-step retrosynthesis prediction algorithms:

**Template-Based Models (from ASKCOS):**
- Pistachio ringbreaker
- BKMS metabolic (trained on enzymatic reactions)
- Reaxys (trained on organic reactions)
- Reaxys biocatalysis (trained on enzymatic reactions)

**Template-Free Models:**
- Integration with BioNavi-NP methodology

**Database Comparison:**
- Chemical reaction template set: 163,723 templates
- Enzymatic reaction template set: 7,984 templates
- BKMS enzymatic reactions include 4,196 unique transformations not found in the synthetic dataset

### 4. Reaction Condition Prediction: Parrot Model

ChemEnzyRetroPlanner embeds two reaction condition recommendation models:
- **RCR (Reaction Condition Recommender):** Trained on Reaxys
- **Parrot:** Trained on USPTO-Condition

**Parrot Architecture:**
- **Part 1 - Chemical Context Prediction:** Causal multitask multiclassification for catalysts, 2 solvents, and 2 reagents
- **Part 2 - Temperature Prediction:** Regression problem
- **Encoder:** BERT model embeds reaction information directly from SMILES (reactants >> products)
- **Decoder:** Predicts 5 contextual reaction conditions in first 5 steps, then combines with encoder output for temperature prediction
- **Interpretability:** Attention mechanisms illustrate correlation between reaction substructures and predicted conditions

### 5. EasIFA: Enzyme Active Site Annotation

EasIFA is a multi-modal deep learning framework for enzyme active site annotation:

**Architecture:**
- Fuses latent enzyme representations from Protein Language Model and 3D structural encoder
- Aligns protein-level information with enzymatic reaction knowledge using multi-modal cross-attention

**Innovations:**
1. Integration of PLMs with structure-based representation
2. Atom-wise distance-aware attention mechanism-based lightweight graph neural network
3. Attention-based interpretable information interaction network

**Performance:**
- 10-fold speed increase over BLASTp
- Improved metrics: +7.57% recall, +13.08% precision, +9.68% F1 score, +0.1012 MCC
- ~1400-fold inference speed increase compared to PSSM-based graph network algorithms

### 6. LLM-Based Agent System

The platform utilizes **Llama3.1:70b** in a chain-of-thought approach to:
- Leverage multiple computational tools
- Construct an agent capable of executing hybrid enzymatic-organic synthesis planning tasks
- Autonomously activate hybrid synthesis strategies for diverse scenarios

---

## Main Results and Contributions

### Benchmark Performance

| Method | Pathway Resolution Success Rate |
|--------|--------------------------------|
| **ChemEnzyRetroPlanner (template-based)** | **64.4%** |
| RetroPathRL (best template-based benchmark) | 59.8% |
| RetroBioCat | < 64.4% |
| ASKCOS | < 64.4% |
| Original Retro* | < 64.4% |
| **ChemEnzyRetroPlanner (template-free)** | **98.4%** |

### Key Contributions

1. **Novel Retro-Rollout* Algorithm:** Outperforms existing retrosynthetic planning tools across multiple benchmark datasets

2. **Hybrid Organic-Enzymatic Integration:** First comprehensive platform combining organic synthesis with enzymatic catalysis in automated planning

3. **Template-Free Enzyme Recommendation:** Overcomes limitations of template-based approaches through EasIFA integration

4. **LLM-Driven Automation:** Chain-of-thought reasoning with Llama3.1 enables autonomous strategy selection

5. **Modular API Design:** Each computational module can be independently invoked for customized synthesis planning scenarios

6. **Open-Source Availability:** Fully open-source platform with web interface and programmatic APIs

### Demonstrated Applications

Chemoenzymatic synthetic routes planned for:
- Sitagliptin (diabetes drug)
- Rivastigmine (Alzheimer's drug)
- Key intermediate for angiotensin 1-converting enzyme inhibitors
- Ephedrine
- (R)-o-chloromandelic acid
- Rasagiline (Parkinson's drug)
- S-Metalochlor (herbicide)

---

## Limitations

### 1. Not MILP-Based Optimization

ChemEnzyRetroPlanner uses neural network-guided tree search (Retro-Rollout*) rather than Mixed Integer Linear Programming (MILP) approaches. While this enables efficient heuristic search, it differs from optimization-based methods like:

- **minChemBio:** Uses MILP for optimal searching through chemical and enzymatic steps
- **NovoStoic:** Utilizes template-based reaction formalization within a stoichiometric modeling framework coupled with MILP

The tree search approach prioritizes finding feasible routes rather than globally optimal solutions.

### 2. No Cost Data Integration

The platform does not incorporate:
- Chemical pricing information for starting materials
- Enzyme production costs
- Reaction operation costs
- Overall route cost optimization

**Note:** The separate **ChemEnzyRetroPlanner_agent** repository includes a Streamlit-based application with some chemical pricing integration, but this is not part of the core optimization framework.

### 3. No Sensitivity Analysis

The publication does not include:
- Systematic sensitivity analysis of algorithm parameters
- Robustness analysis across different datasets
- Uncertainty quantification in route predictions
- Analysis of prediction confidence bounds

### 4. Limited Enzymatic Reaction Coverage

- The scarcity of enzymatic reaction data hinders the ability of single-step retrosynthesis models for enzymatic reactions to support search algorithms in exploring a wide chemical space effectively
- Template set comparison: 7,984 enzymatic templates vs. 163,723 chemical templates
- This limits the breadth of enzymatic strategies compared to organic synthesis options

### 5. Wet Lab Validation Gap

- The search success rate metric does not verify whether the searched synthetic route can be executed in the wet lab
- This limitation is particularly problematic for targets requiring long synthetic routes, where errors can accumulate across multiple steps

### 6. Template-Based Enzyme Recommendation Limitations

- Current enzymatic synthesis planning algorithms face challenges due to reliance on template-based enzyme recommendations
- This limits adaptability across diverse scenarios (though EasIFA partially addresses this)

---

## Code Repositories

### Primary Repository

**ChemEnzyRetroPlanner**
- **GitHub:** [https://github.com/wangxr0526/ChemEnzyRetroPlanner](https://github.com/wangxr0526/ChemEnzyRetroPlanner)
- **Zenodo Archive:** [https://zenodo.org/records/1733174757](https://zenodo.org/records/1733174757)
- **License:** MIT
- **Language Composition:** Python (80.1%), CSS (9.7%), HTML (8.0%), Shell (2.1%)
- **Version:** v1.0 (October 2025)

### Agent Interface Repository

**ChemEnzyRetroPlanner_agent**
- **GitHub:** [https://github.com/wangxr0526/ChemEnzyRetroPlanner_agent](https://github.com/wangxr0526/ChemEnzyRetroPlanner_agent)
- **Zenodo Archive:** [https://doi.org/10.5281/zenodo.1741645658](https://doi.org/10.5281/zenodo.1741645658)
- **License:** MIT
- **Features:** Streamlit-based application with chemical pricing integration

### Related Repositories by the Authors

| Repository | Description | URL |
|------------|-------------|-----|
| **RetroPrime** | Single-step retrosynthesis model | [github.com/wangxr0526/RetroPrime](https://github.com/wangxr0526/RetroPrime) |
| **Parrot** | Reaction condition prediction | [github.com/wangxr0526/Parrot](https://github.com/wangxr0526/Parrot) |
| **EasIFA** | Enzyme active site annotation | [github.com/wangxr0526/EasIFA](https://github.com/wangxr0526/EasIFA) |

### Web Servers

- **Primary Server:** [http://cadd.zju.edu.cn/retroplanner](http://cadd.zju.edu.cn/retroplanner)
- **Mirror/Backup:** [http://cadd.iddd.group/retroplanner/](http://cadd.iddd.group/retroplanner/)
- **EasIFA Server:** [http://easifa.iddd.group](http://easifa.iddd.group)

**Note:** Public servers may experience heavy load; local deployment is recommended for large jobs.

### System Requirements

- **Operating System:** Linux
- **Python:** >= 3.8
- **PyTorch:** 2.1.2 (CUDA 12.1)
- **DGL:** 2.0.0 (CUDA 12.1)
- **RDKit:** 2022.9.5
- **NumPy:** >= 1.23.5
- **Pandas:** 1.4.4

### Installation

Three-step setup workflow:
1. Clone repository and run setup script (`setup_ChemEnzyRetroPlanner.sh`)
2. Build Parrot service Docker image via `build_parrot_in_docker.sh`
3. Start services using `run_container.sh`

Local server deploys to `http://localhost:8001/retroplanner`

---

## Summary

ChemEnzyRetroPlanner represents a significant advancement in computer-aided synthesis planning by integrating organic and enzymatic catalysis strategies within a unified AI-driven framework. The Retro-Rollout* algorithm demonstrates superior performance over existing tools like RetroPathRL, RetroBioCat, and ASKCOS. The platform's modular design, combining multiple neural network models (for retrosynthesis, condition prediction, and enzyme annotation) with an LLM-based agent system, provides a comprehensive solution for chemoenzymatic route planning.

Key strengths include the open-source nature, extensive web interface, and programmatic APIs. However, limitations such as the absence of MILP-based optimization, lack of cost data integration, and missing sensitivity analysis should be considered when comparing against other retrosynthesis tools for specific applications.

---

## References

1. Wang, X., Yin, X., Zhang, X., et al. (2025). A virtual platform for automated hybrid organic-enzymatic synthesis planning. *Nature Communications*. DOI: [10.1038/s41467-025-65898-3](https://doi.org/10.1038/s41467-025-65898-3)

2. Chen, B., Li, C., Dai, H., & Song, L. (2020). Retro*: Learning Retrosynthetic Planning with Neural Guided A* Search. *ICML 2020*. [arXiv:2006.15820](https://arxiv.org/abs/2006.15820)

3. Wang, X., et al. (2024). Multi-modal deep learning enables efficient and accurate annotation of enzymatic active sites. *Nature Communications*. DOI: [10.1038/s41467-024-51511-6](https://doi.org/10.1038/s41467-024-51511-6)

---

*Report generated for AIchemy research documentation.*

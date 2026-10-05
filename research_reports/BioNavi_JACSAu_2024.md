# BioNavi: Hybrid Retrosynthesis Planning for Chemoenzymatic Synthesis

## Research Report

---

## Full Citation

**Title:** Developing BioNavi for Hybrid Retrosynthesis Planning

**Authors:** Tao Zeng, Zhehao Jin, Shuangjia Zheng, Tao Yu, and Ruibo Wu*

**Journal:** JACS Au

**Year:** 2024

**Volume/Issue:** 4(7), 2492-2502

**DOI:** [10.1021/jacsau.4c00228](https://doi.org/10.1021/jacsau.4c00228)

**Publication Date:** July 3, 2024

**PMID:** 39055138

**Author Affiliations:**
- Tao Zeng, Ruibo Wu - School of Pharmaceutical Sciences, Sun Yat-sen University, Guangzhou 510006, P. R. China
- Zhehao Jin, Tao Yu - Center for Synthetic Biochemistry, CAS Key Laboratory of Quantitative Engineering Biology, Shenzhen Institute of Synthetic Biology, Shenzhen Institutes of Advanced Technology, Chinese Academy of Sciences (CAS), Shenzhen 518055, P. R. China
- Shuangjia Zheng - Global Institute of Future Technology, Shanghai Jiao Tong University, Shanghai 200240, P. R. China

---

## Abstract/Overview

Illuminating synthetic pathways is essential for producing valuable chemicals, such as bioactive molecules. Chemical and biological syntheses are crucial, and their integration often leads to more efficient and sustainable pathways. Despite the rapid development of retrosynthesis models, few of them consider both chemical and biological syntheses, hindering the pathway design for high-value chemicals.

BioNavi is proposed by innovating **multitask learning** and **reaction templates** into a deep learning-driven model to design hybrid synthesis pathways in a more interpretable manner. BioNavi outperforms existing approaches on different data sets, achieving a **75% hit rate** in replicating reported biosynthetic pathways and displaying superior ability in designing hybrid synthesis pathways.

The enhanced web server simplifies input operations and implements step-by-step exploration according to user experience. BioNavi is shown to be a handy navigator for designing synthetic pathways for various chemicals.

---

## Key Methodology

### Data Processing and Template Extraction

- **Dataset Size:** 75,012 enzymatic and 889,557 nonenzymatic reactant-product pairs from public databases
- **Template Extraction:** 6,027 enzymatic and 119,632 nonenzymatic reaction templates extracted
- **Atom-Atom Mapping Strategy:** Removes cofactors while preserving necessary reactants for specific products

### Model Architecture

1. **Transformer-based Single-Step Prediction Model**
   - Product input, reactants output in end-to-end manner
   - Deep learning-based language model trained from reaction pairs
   - No templates required for prediction (template-free approach for single-step)

2. **Multitask Learning with Weighted Training**
   - 1:4 ratio for biological:chemical datasets to balance prediction accuracy
   - Automatic reaction type indication (chemical vs biological) during pathway search
   - Multilabel prediction outputting reactants along with reaction type labels

3. **Ensemble Model**
   - Four models trained with different hyperparameters/random seeds
   - Combined for improved prediction reliability

4. **Reaction Feasibility Scoring**
   - Integrates template-based validation
   - Makes predictions more interpretable
   - Guides enzyme selection

### Search Strategy

- **Retro* Algorithm:** For multistep pathway planning
- **Bayesian Scoring Mechanism:** Combines model probability with template support metrics
- **A* Search:** Informed graph traversal algorithm for pathfinding and optimization
  - Considers both cost-so-far (historical cost) and estimated cost-to-go (future cost)
  - Finds optimal path while minimizing total cost

---

## Main Results and Contributions

### Performance Metrics

| Metric | Natural Products | Drugs |
|--------|------------------|-------|
| Success Rate | 97.0% | 76.4% |
| Hit Rate | 75.0% | N/A |
| Average Solutions | 9.5 | 9.7 |
| Runtime (minutes) | 4.4 | 10.9 |

### Key Achievements

1. **Superior Hybrid Pathway Generation**
   - **64.7%** of pathways predicted by BioNavi are hybrid
   - Significantly higher than ASKCOS (42.9%)
   - More diverse pathway outputs for drug molecules

2. **High Biosynthetic Pathway Replication**
   - 75% hit rate in replicating reported biosynthetic pathways
   - Outperforms existing approaches on multiple datasets

3. **Interpretability**
   - Template integration enables interpretable predictions
   - Users can explore pathways according to score, enzyme information, or personal experience

### Case Studies

1. **Nirmatrelvir (COVID-19 drug)**
   - Predicted pathway ranks third among solutions
   - Successfully reproduces key intermediates
   - Proposes alternative N-protection strategies

2. **Jomthonic acid A**
   - Generated chemoenzymatic pathways matching recent experimental work
   - Demonstrates practical applicability

3. **Syringic acid**
   - Designed simplified biosynthetic route
   - Experimental verification partially validated predictions

### Comparison with ASKCOS

- BioNavi generates more hybrid pathways (64.7% vs 42.9%)
- Template-free approach captures reaction patterns beyond predefined databases
- More flexible than ASKCOS's template-dependent methodology

---

## Limitations

### Explicitly Acknowledged in Paper

1. **Data Quality Issues**
   - Dataset predominantly contains experimentally validated reactions (positive data only)
   - Stereochemistry often incomplete in biological reaction databases
   - Complex structures (RiPPs, NRPs with >3 building blocks) show lower hit rates

2. **Implementation Gaps**
   - Reaction condition prediction remains separate from pathway planning
   - Enzyme engineering necessary for implementing predicted pathways
   - No integrated enzyme expression/optimization guidance

3. **Performance Variability**
   - Amino acid category showed lowest hit rates (18.3% and 46.2%)
   - Diverse building blocks in complex structures reduce prediction accuracy

### Notable Limitations NOT Addressed

1. **No MILP (Mixed Integer Linear Programming) Optimization**
   - BioNavi does not use MILP-based pathway optimization
   - Cannot formulate pathway selection as a mathematical optimization problem
   - No constraint-based reasoning for metabolic network analysis

2. **No Cost Modeling**
   - Lacks economic feasibility scoring
   - No integration of reagent costs, enzyme production costs, or process economics
   - Does not consider atom economy optimization (unlike newer tools like RetroScore)
   - No consideration of:
     - Raw material costs
     - Enzyme expression costs
     - Scale-up feasibility
     - Process development costs

3. **No Yield Prediction**
   - Does not predict reaction yields
   - No flux balance analysis integration
   - Cannot estimate overall pathway efficiency

4. **Limited Optimization Framework**
   - Scoring based on model probability and template support only
   - No multi-objective optimization for sustainability metrics
   - No consideration of green chemistry principles beyond pathway design

---

## Code Repositories and Resources

### Primary Repository (JACS Au 2024 Paper)

**GitHub:** [https://github.com/zengtsysu/BioNavi](https://github.com/zengtsysu/BioNavi)

- **License:** MIT
- **Language:** Python (96.7%), Shell (3.3%)
- **Stars:** 12 | **Forks:** 4

**Installation:**
```bash
sudo apt-get install graphviz  # optional for visualization
conda create -n bionavi python==3.7
conda activate bionavi
sh install.sh
```

**Key Components:**
- `run_bionavi.py` - Single molecule planning
- `run_bionavi_batch.py` - Batch test set evaluation
- `script/eval_pathway.py` - Pathway prediction assessment
- `config/bionavi_conf.yaml` - Configuration file
- Pre-trained ensemble models available for download

### Predecessor Repository (BioNavi-NP)

**GitHub:** [https://github.com/prokia/BioNavi-NP](https://github.com/prokia/BioNavi-NP)

- Source code for "Deep Learning Driven Biosynthesis Pathways Navigation for Natural Products with BioNavi-NP" (Nature Communications 2022)
- Requires: Anaconda with Python 3.7+, CUDA toolkit 11.1
- Tested on Ubuntu 18.04 with Nvidia RTX3090

### Web Server

**URL:** [http://biopathnavi.qmclab.com/bionavi/](http://biopathnavi.qmclab.com/bionavi/)

Features:
- Simplified input operations
- Step-by-step pathway exploration
- Interactive visualization of predicted pathways
- Sorting by computational cost, length, and organism-specific enzymes

---

## Related Work and Context

### Predecessor: BioNavi-NP (2022)

- Published in Nature Communications
- Focused on natural products biosynthesis
- Used MCTS-based search (achieved 34.8% success rate)
- BioNavi (2024) improved upon this with Retro* algorithm

### Competing Tools

1. **ASKCOS** - Chemical synthesis planner with enzymatic step identification
2. **RTS-CESP** - Reaction type score-guided chemoenzymatic synthesis planning
3. **READRetro** - Retrieval-augmented dual-view retrosynthesis for natural products

### Citation

```bibtex
@article{zeng2024bionavi,
  title={Developing BioNavi for Hybrid Retrosynthesis Planning},
  author={Zeng, Tao and Jin, Zhehao and Zheng, Shuangjia and Yu, Tao and Wu, Ruibo},
  journal={JACS Au},
  volume={4},
  number={7},
  pages={2492--2502},
  year={2024},
  publisher={American Chemical Society},
  doi={10.1021/jacsau.4c00228}
}
```

---

## Summary

BioNavi represents a significant advancement in hybrid (chemoenzymatic) retrosynthesis planning, combining deep learning with reaction templates for interpretable pathway design. Its key innovation is the multitask learning approach that balances chemical and biological reaction prediction, resulting in 64.7% hybrid pathway generation compared to 42.9% for ASKCOS.

However, BioNavi operates primarily as a pathway enumeration and ranking tool based on learned reaction patterns. It does not incorporate:
- MILP-based mathematical optimization
- Economic cost modeling
- Yield prediction
- Multi-objective optimization for sustainability

These limitations suggest opportunities for future tools that integrate BioNavi's strong pathway prediction capabilities with rigorous optimization frameworks for practical process development.

---

*Report generated: February 2026*

*Sources: JACS Au, PubMed Central, GitHub*

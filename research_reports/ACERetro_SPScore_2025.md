# ACERetro & SPScore: Chemoenzymatic Synthesis Planning Guided by Synthetic Potential Scores

## Research Report

**Date:** February 26, 2026

---

## Full Citation

Liu, X., Li, H., & Zhao, H. (2025). Chemoenzymatic synthesis planning guided by synthetic potential scores. *Digital Discovery*, 4, 2534-2547.

**DOI:** [10.1039/D5DD00008D](https://doi.org/10.1039/D5DD00008D)

**Article Timeline:**
- Received: January 8, 2025
- Accepted: July 23, 2025
- Published: 2025

**Authors and Affiliations:**
- **Xuan Liu, Hongxiang Li, and Huimin Zhao**
  - NSF Molecule Maker Lab Institute, University of Illinois at Urbana-Champaign
  - Department of Chemical and Biomolecular Engineering, University of Illinois at Urbana-Champaign
  - Carl R. Woese Institute for Genomic Biology, University of Illinois at Urbana-Champaign
  - Department of Chemistry, University of Illinois at Urbana-Champaign
  - DOE Center for Advanced Bioenergy and Bioproducts Innovation

---

## Abstract/Overview

This research presents a unified framework for computer-aided chemoenzymatic synthesis planning by introducing the **Synthetic Potential Score (SPScore)**. The SPScore evaluates the potential of enzymatic or organic reactions for molecule synthesis, bridging previously separate planning strategies (step-by-step and bypass approaches).

The SPScore integrates with **ACERetro** (Asynchronous ChemoEnzymatic Retrosynthesis), an asynchronous retrosynthesis algorithm that achieves **46% more successful route discoveries** than current state-of-the-art methods across a test dataset of 1001 molecules. The methodology was validated through the design of chemoenzymatic synthesis routes for FDA-approved drugs including ethambutol and Epidiolex.

---

## Key Methodology

### 1. Synthetic Potential Score (SPScore) Development

#### Training Data
- **Organic reactions:** 437,781 product molecules from USPTO 480K
- **Enzymatic reactions:** 37,939 product molecules from ECREACT
- **Overlap:** 515 molecules present in both categories

#### Molecular Representation
- Evaluated ECFP4 and MAP4 fingerprints at lengths of 1024, 2048, and 4096 bits
- **Optimal configuration:** ECFP4 embedding of 4096 length with 3 hidden layers

#### Model Architecture
- Multilayer perceptron (MLP) trained using margin ranking loss (margin = 0.15)
- Generates two continuous scores:
  - **SChem:** Synthetic potential for organic reactions
  - **SBio:** Synthetic potential for enzymatic reactions
- Preference learning approach rather than binary classification

#### Prediction Accuracy
Predictions evaluated by checking score rankings against thresholds:
- Organic reactions: SChem > SBio + margin
- Enzymatic reactions: SBio > SChem + margin
- Both reaction types: |SChem - SBio| < margin

### 2. ACERetro Algorithm

#### Comparative Approaches
| Method | Strategy | Results (1001 molecules) |
|--------|----------|--------------------------|
| **FHSync** | Fully Hybrid Synchronous - searches both reaction types simultaneously without SPScore guidance | 597 molecules |
| **SPSync** | SPScore-guided Synchronous - selects single most promising reaction type | 683 molecules |
| **ACERetro** | SPScore-guided Asynchronous - maintains alternative pathways in queue | **720 molecules** |

#### Search Scoring Formula
```
Scorei = (1 - c * SPScorei)^d * f(P)
```
Where:
- i in [Chem, Bio]
- c = reaction type exploration factor
- d = depth exploration factor
- f(P) = molecular complexity function

#### Search Parameters
- Maximum search depth: 10
- Expansion time limit: 180 seconds
- Buyable compound sources: eMolecules and Sigma-Aldrich databases

#### Retrosynthesis Tools Integration
- **Organic reactions:** RXN4Chemistry (template-free)
- **Enzymatic reactions:** ASKCOS with Levin et al.'s enzymatic templates (template-based)

---

## Main Results and Contributions

### 1. Performance Improvements

| Metric | Value |
|--------|-------|
| Improvement vs. Levin et al. baseline | +46.0% more molecules found |
| Improvement vs. FHSync | +20.6% |
| Improvement vs. SPSync | +5.4% |

### 2. Route Quality Analysis
For 466 molecules where both ACERetro and baseline found routes:
- **35.8%** yielded shorter optimized routes with ACERetro
- **55.8%** produced equivalent-length routes
- **26x** more exclusive molecule discoveries than baseline

### 3. SPScore Validation
Multi-step retrosynthesis validation using 493 molecules:
- **85.8%** of molecules in shortest routes had synthesis fields covered by SPScore predictions
- **89.9%** of reactions in shortest routes retained predicted reaction types
- **79.7%** of target molecules retained at least one consistent shortest route

### 4. FDA Drug Case Studies

#### (S,S)-Ethambutol (Tuberculosis Treatment)
- Novel route establishing chiral center through enzymatic aminotransferase reaction
- Starting from cheap 2-butanone
- Integration of acylation and CYP124 enzyme-catalyzed hydroxylation
- Milder reaction conditions compared to existing chemical syntheses

#### Epidiolex ((-)-Cannabidiol, Epilepsy Treatment)
- Concise two-step route predicted:
  1. Alkylation of olivetol with geraniol
  2. Enzymatic conversion using cannabidiolic acid synthase (CBDAS)

#### Rivastigmine (Dementia Drug)
- SPScore identified optimization candidate intermediate
- Discovered validated enzymatic transformation using identical starting materials

#### (R,R)-Formoterol
- Three optimization opportunities identified
- One-step organic synthesis replaced three-step enzymatic approach

### 5. Key Contributions
1. **Unified Framework:** Transforms chemoenzymatic synthesis planning from a fragmented process into a unified framework
2. **SPScore Metric:** Novel scoring system for evaluating enzymatic vs. organic reaction suitability
3. **Asynchronous Search:** Maintains alternative pathways for improved robustness
4. **Template-free Integration:** Compatible with any existing retrosynthesis tool

---

## Limitations

### 1. Model Architecture Limitations
- Current approach uses simplified molecular fingerprints (ECFP4) and standard neural networks
- Future work could incorporate more complex models such as molecular graphs and reinforcement learning

### 2. Data Quality Dependency
- Model performance depends critically on comprehensive and high-quality datasets
- USPTO reactions are confined to patents and differ in distribution from literature reactions
- ECREACT database has inherent biases toward certain enzyme classes

### 3. Enzymatic Database Constraints
- Limited knowledge transfer from general chemical space
- Incomplete enzyme assignment in databases
- Enzymatic reaction databases (like BKMS-react) biased towards metabolic enzymes
- Reduced capability for human-made molecules not similar to natural products

### 4. Computational Challenges
- Potentially exponential search space during retrosynthesis planning
- Runtime limitations for large-scale molecule screening
- Search success rate metric may be overly lenient

### 5. Practical Validation Gaps
- Predicted routes may not be directly translatable to wet lab synthesis
- Data-driven retrosynthesis models can predict unrealistic or hallucinated reactions
- Enzyme stability constraints (temperature, pH, pressure) not fully characterized in predictions

### 6. Template Dependencies
- Enzymatic reactions rely on template-based ASKCOS, limiting discovery of novel transformations
- Template prioritization system constraints affect pathway diversity

---

## Code Repositories and Resources

### GitHub Repository
**URL:** [https://github.com/Zhao-Group/ACERetro](https://github.com/Zhao-Group/ACERetro)

**License:** MIT

**Key Components:**
| Directory | Purpose |
|-----------|---------|
| `sfscore/` | Score computation module |
| `process_reaction_database/` | Training data preparation, fingerprint embedding, model training |
| `pathway_search_standalone/` | Hybrid synthesis pathway search implementation |
| `evaluate_score/` | Benchmarking scripts against ZINC and ASKCOS results |
| `lib/`, `data/` | Supporting libraries and datasets |

**Dependencies:**
- Python 3.9.12
- PyTorch 1.12.1
- RDKit (rdkit-pypi==2022.3.5)
- NumPy 1.21.5
- MAP4 1.0 (optional)

**Quick Start:**
```python
from sfscore import SFScore
model = SFScore()
model.load()
score = model.score_from_smi('O=C(COP(=O)(O)O)[C@H](O)[C@H](O)CO')
```

**Pathway Search:**
```python
from scripts.search_utils import hybridSearch
searcher = hybridSearch()
results = searcher.get_chemoenzy_path_async(smiles, max_depth=10, time_lim=180)
```

### Web Interface
**URL:** [https://aceretro.platform.moleculemaker.org/search-routes](https://aceretro.platform.moleculemaker.org/search-routes)

A user-friendly web interface for running ACERetro searches without local installation.

### Archived Data
**Zenodo DOI:** [10.5281/zenodo.10578664](https://doi.org/10.5281/zenodo.10578664)

---

## Related Work

### Predecessor Work
- Levin et al. (2023). "Computer-assisted multistep chemoenzymatic retrosynthesis using a chemical synthesis planner." *Chemical Science*. DOI: 10.1039/D3SC01355C

### Related Paper by Same Authors
- Liu et al. (2024). "Chemoenzymatic Synthesis Planning Guided by Reaction Type Score." *Journal of Chemical Information and Modeling*. DOI: 10.1021/acs.jcim.4c01525

---

## Sources

- [Digital Discovery Article (RSC Publishing)](https://pubs.rsc.org/en/content/articlelanding/2025/dd/d5dd00008d)
- [Full Paper PDF (Zhao Group)](https://zhaogroup.chbe.illinois.edu/publications/HZ466.pdf)
- [Digital Discovery HTML Version](https://pubs.rsc.org/en/content/articlehtml/2025/dd/d5dd00008d)
- [GitHub: Zhao-Group/ACERetro](https://github.com/Zhao-Group/ACERetro)
- [ACERetro Web Interface](https://aceretro.platform.moleculemaker.org/search-routes)

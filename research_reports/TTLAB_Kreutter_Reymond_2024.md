# TTLAB: Chemoenzymatic Multistep Retrosynthesis with Transformer Loops

## Research Report

**Report Generated:** February 26, 2026

---

## Full Citation

Kreutter, D.; Reymond, J.-L. Chemoenzymatic Multistep Retrosynthesis with Transformer Loops. *Chem. Sci.* **2024**, *15*(43), 18031-18047.

- **DOI:** [10.1039/D4SC02408G](https://doi.org/10.1039/D4SC02408G)
- **PMID:** 39416295
- **PMCID:** PMC11474389
- **Authors:** David Kreutter, Jean-Louis Reymond
- **Affiliation:** Department of Chemistry, Biochemistry and Pharmaceutical Sciences, University of Bern, Freiestrasse 3, 3012 Bern, Switzerland
- **Received:** April 11, 2024
- **Accepted:** October 7, 2024
- **Published:** October 8, 2024
- **License:** Creative Commons Attribution 3.0 Unported Licence

---

## Abstract/Overview

The paper introduces **TTLAB (Triple Transformer Loop Algorithm with Biocatalysis)**, a novel computer-aided synthesis planning (CASP) tool designed for chemoenzymatic multistep retrosynthesis. The key innovation is the integration of enzymatic reactions into retrosynthetic planning, which should enable the design of more selective, economical, and environmentally friendly (greener) synthetic routes.

TTLAB performs single-step retrosynthesis using two parallel triple transformer loops (TTL):
1. **USPTO-TTL:** Trained on 1.27 million chemical reactions from the US Patent Office
2. **ENZR-TTL:** Obtained through multitask transfer learning combining the USPTO dataset with 57,176 preparative biotransformations from the Reaxys literature

Each TTL operates independently through a three-stage process:
- **T1:** Predicts possible starting materials from tagged products
- **T2:** Predicts reagents (for chemical reactions) or enzyme descriptions (for biotransformations)
- **T3:** Validates predictions via forward synthesis prediction

The system combines predictions from both TTLs using a heuristic best-first tree search to explore multistep sequences and propose short routes from commercial building blocks, including enantioselective biocatalytic steps.

---

## Key Methodology

### Dataset Construction

| Dataset | Size | Source |
|---------|------|--------|
| USPTO | 1.27 million reactions | US Patent Office chemical reactions |
| ENZR | 57,176 reactions | Reaxys preparative biotransformations |
| Building Blocks | 534,058 compounds | MolPort and Enamine commercially available compounds |

### Model Architecture

The TTLAB system employs a sophisticated multi-transformer architecture:

1. **AutoTag Model (T0):** Identifies potential reactive disconnection sites in product molecules by tagging atoms that could serve as reaction centers

2. **Retrosynthesis Model (T1):** Predicts starting materials from tagged product molecules using SMILES representation

3. **Reagent/Enzyme Prediction Model (T2):** Predicts reagents for chemical reactions or enzyme descriptions for biotransformations

4. **Forward Validation Model (T3):** Validates proposed retrosynthetic steps by predicting the forward reaction and comparing to the original product

### Training Innovation

The system uses **multitask transfer learning** with instruction tokens ("ENZYME" and "USPTO") to help models distinguish between chemical and enzymatic reaction prediction tasks. This approach improves accuracy and prevents task ambiguity when the same model handles both reaction types.

### Tree Search Strategy

TTLAB employs a **heuristic best-first tree search** guided by route penalty scoring to explore multistep retrosynthetic pathways. The search terminates when all precursors are commercially available building blocks.

---

## Main Results and Contributions

### Single-Step Retrosynthesis Performance

| Metric | USPTO-TTL | ENZR-TTL |
|--------|-----------|----------|
| Top-1 Round-trip Accuracy | 81.3% | 59.0% |
| Top-3 Accuracy (single-atom tags) | - | 76.2% |
| Confidence Threshold | 90% | 90% |

### Multistep Route Prediction Success Rates

| Test Set | Molecules Tested | Successful Routes | Success Rate |
|----------|------------------|-------------------|--------------|
| USPTO Test | 100 | 88 | 88% |
| ENZR Test | 80 | 61 | 76% |
| Caspyrus Dataset | 1,000 | 852 | 85% |

### Enzymatic Step Integration

In successful routes:
- **8-9%** of steps are enzyme-catalyzed for general molecules (USPTO/Caspyrus datasets)
- **17-50%** of steps are enzyme-catalyzed for specialized enzymatic targets (ENZR dataset)

### Pharmaceutical Applications

TTLAB successfully predicted chemoenzymatic routes for three clinically important drugs:

1. **Atorvastatin** (cholesterol-lowering drug): Four-step sequence using aldo-keto reductase for stereoselective reduction

2. **(S)-Duloxetine** (antidepressant): Single-step enzymatic demethylation using laccase

3. **Sitagliptin** (diabetes treatment): Single-step transaminase-catalyzed enantioselective synthesis

### Comparison with Competing Tools

| Tool | Performance |
|------|-------------|
| **IBM RXN for Chemistry** | Failed to identify enzymatic steps despite using biochemical data |
| **ASKCOS** | Successfully identified biocatalytic routes for specific molecules but limited success rate overall |
| **BioNavi** | Produced shorter routes but succeeded on fewer test cases |

### Key Contributions

1. **First practical integration** of preparative biocatalysis data into transformer-based retrosynthesis
2. **Dual-TTL architecture** enabling parallel exploration of chemical and enzymatic pathways
3. **Text-based enzyme descriptions** rather than EC classifications, better reflecting preparative biocatalysis practices
4. **Self-correcting capability:** The transformer models occasionally identified and corrected errors in source databases
5. **Framework for green chemistry:** Systematic exploration of chemoenzymatic pathways for more sustainable manufacturing

---

## Limitations

### Technical Limitations

1. **Performance Gap:** ENZR-TTL significantly underperforms USPTO-TTL (59% vs. 81.3% top-1 accuracy), primarily due to the smaller enzymatic dataset (57K vs. 1.27M reactions)

2. **Enzyme Specificity Constraints:** Enzymatic steps are only selected when the reaction is closely related to a training set reaction, limiting generalization beyond training examples

3. **Confidence Threshold Dependency:** Requires careful calibration of the 90% confidence threshold for validation filtering

4. **Incomplete Training Data:** Some enzymatic reactions in the training set lacked full enzyme documentation or cofactor information

### Data and Accessibility Limitations

5. **Dataset Restrictions:** The Reaxys enzymatic data cannot be publicly released due to commercial licensing, limiting reproducibility

6. **Database Characteristics:** Reaxys enzymatic data represents non-natural substrate conditions that may not always be comparable to biochemical pathway data

7. **Limited Dataset Diversity:** The enzymatic dataset has substantial overlap with USPTO (15.7% shared molecules), while ECREACT biochemical pathway data showed minimal overlap (7.6%), suggesting different molecular spaces

### Algorithmic Limitations

8. **Chemical-Enzymatic Balance:** The system may over-prioritize chemical routes due to the larger USPTO training set

9. **Route Length:** Generated routes may not always be the shortest possible due to tree search heuristics

---

## Code Repositories

### Primary Repository

**GitHub:** [reymond-group/MultiStepRetrosynthesisTTL](https://github.com/reymond-group/MultiStepRetrosynthesisTTL)

#### Repository Features

- **Triple Transformer Loop (TTL)** implementation for disconnection-aware retrosynthesis
- **Tree search strategy** with route penalty scoring
- **Dual pathway support** for chemoenzymatic route prediction
- **Commercial building block integration** (MolPort and Enamine databases)
- **Checkpoint system** for progress monitoring and job resumption

#### Installation Requirements

- Python 3.8.16 (via Conda environment)
- OpenNMT-py (neural machine translation framework)
- SCScore (synthetic complexity assessment)
- RDKit (chemistry operations)
- Pandas (data handling)

#### Pre-trained Models

Four USPTO models are available from Zenodo:
- Auto-Tag model (T0)
- Retrosynthesis model (T1)
- Reagent prediction model (T2)
- Forward validation model (T3)

**Note:** Enzymatic models (ENZR-TTL) require access to the Reaxys commercial database and cannot be publicly distributed.

#### Usage

```bash
# Configure target compound in config file
# Execute retrosynthesis
retrosynthesis --config configs/config_example.yaml

# Results saved to output/project_name/
# - prediction.pkl: Single-step predictions
# - tree.pkl: Complete synthetic pathways
```

#### Visualization

A Jupyter notebook (`visualize_results.ipynb`) provides tools for route analysis, including filtering by confidence scores and branch selection.

---

## Related Publications

- **ChemRxiv Preprint:** [Chemoenzymatic Multistep Retrosynthesis with Transformer Loops](https://chemrxiv.org/engage/chemrxiv/article-details/66e930d412ff75c3a193b6f1)
- **Earlier TTL Work:** Kreutter, D.; Schwaller, P.; Reymond, J.-L. *Chem. Sci.* 2021 (Multistep retrosynthesis combining disconnection aware triple transformer loop)
- **Data Augmentation Extension:** [ChemRxiv 2024](https://chemrxiv.org/doi/full/10.26434/chemrxiv-2024-r3x05-v2)

---

## Sources

- [Chemical Science (RSC Publishing) - Full Article](https://pubs.rsc.org/en/content/articlehtml/2024/sc/d4sc02408g)
- [PubMed Entry](https://pubmed.ncbi.nlm.nih.gov/39416295/)
- [PMC Full Text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11474389/)
- [GitHub Repository](https://github.com/reymond-group/MultiStepRetrosynthesisTTL)
- [ChemRxiv Preprint](https://chemrxiv.org/engage/chemrxiv/article-details/66e930d412ff75c3a193b6f1)

---

*This report was compiled from publicly available sources including the published article, PubMed/PMC records, and the associated GitHub repository.*

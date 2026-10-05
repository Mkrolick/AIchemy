# Retro-fallback: Retrosynthetic Planning in an Uncertain World

## Full Citation

**Title:** Retro-fallback: Retrosynthetic Planning in an Uncertain World

**Authors:**
- Austin Tripp (University of Cambridge)
- Krzysztof Maziarz (Microsoft Research AI4Science)
- Sarah Lewis (Microsoft Research AI4Science)
- Marwin Segler (Microsoft Research AI4Science)
- Jose Miguel Hernandez-Lobato (University of Cambridge)

**Venue:** International Conference on Learning Representations (ICLR) 2024 - Poster Session

**Publication Date:** January 16, 2024 (Camera-ready); Poster Session: May 8, 2024

**Links:**
- arXiv: [https://arxiv.org/abs/2310.09270](https://arxiv.org/abs/2310.09270)
- OpenReview: [https://openreview.net/forum?id=dl0u4ODCuW](https://openreview.net/forum?id=dl0u4ODCuW)
- ICLR Proceedings: [https://proceedings.iclr.cc/paper_files/paper/2024/hash/828c6d69bdf91fca7f2b97c4dc214e94-Abstract-Conference.html](https://proceedings.iclr.cc/paper_files/paper/2024/hash/828c6d69bdf91fca7f2b97c4dc214e94-Abstract-Conference.html)

**Keywords:** Retrosynthesis, planning, chemistry, search

---

## Abstract / Overview

Retrosynthesis is the task of planning a series of chemical reactions to create a desired molecule from simpler, buyable molecules. While previous works have proposed algorithms to find optimal solutions for a range of metrics (e.g., shortest path, lowest-cost), these works generally overlook the fact that we have imperfect knowledge of the space of possible reactions, meaning plans created by algorithms may not work in a laboratory.

The paper proposes a novel formulation of retrosynthesis in terms of **stochastic processes** to account for this uncertainty. The authors introduce an evaluation metric called **Successful Synthesis Probability (SSP)** which quantifies the probability that at least one synthesis plan found by an algorithm will work. This naturally captures the idea of producing backup plans.

The authors then propose a novel greedy algorithm called **retro-fallback** which maximizes the probability that at least one synthesis plan can be executed in the lab. Using in-silico benchmarks, they demonstrate that retro-fallback generally produces better sets of synthesis plans than the popular MCTS and retro* algorithms.

---

## Key Methodology

### 1. Stochastic Process Formulation

The core insight is that uncertainty about whether a synthesis plan will work in the wet lab can be quantified using stochastic processes. The paper introduces two key stochastic models:

#### Feasibility Model
- For reactions, the authors postulate the existence of an unknown "feasibility" function: **f*: R -> {0, 1}**
- A **feasibility model** xi_f is defined as a binary stochastic process over the space of reactions R
- This captures the uncertainty about whether a predicted reaction will actually work in practice

#### Buyability Model
- For molecules, they postulate an unknown "buyability" function: **b*: M -> {0, 1}**
- A **buyability model** xi_b is defined as a binary stochastic process over the space of molecules M
- This captures uncertainty about whether a molecule can actually be purchased

The approach collapses nuance into binary outcomes: reactions are either feasible or infeasible, and molecules are either buyable or not.

### 2. AND/OR Graph Structure

The formulation uses AND/OR graphs to represent synthesis plans:
- **Reactions (AND nodes):** For a reaction r to succeed, it must be feasible (f(r) = 1) AND all its reactant molecules must succeed
- **Molecules (OR nodes):** A molecule m will succeed if it is buyable (b(m) = 1) OR if any reaction producing it succeeds

### 3. Successful Synthesis Probability (SSP)

The **Successful Synthesis Probability (SSP)** is the key evaluation metric. It quantifies the probability that an algorithm's output contains at least one feasible synthesis route.

Key properties:
- SSP naturally captures the value of backup/fallback plans
- The exact computation of SSP is proven to be **NP-hard**
- In practice, SSP is estimated through Monte Carlo sampling (e.g., k = 10,000 samples)

### 4. Retro-fallback Algorithm (Greedy Search)

The retro-fallback algorithm is a greedy search that maximizes SSP:

**Algorithm Overview:**
1. **Initialization:** Initialize the AND/OR graph G'
2. **Iteration:** Perform L iterations of expansion
3. **Value Computation:** In each iteration, compute values of s, psi, and rho for each sample of f and b
4. **Termination Check:** Check if there are no frontier nodes OR if estimated SSP = 100%
5. **Node Selection:** Select a frontier node maximizing alpha (contribution to SSP)
6. **Expansion:** Expand the selected node

**Key Features:**
- Works on a minimal AND/OR graph (more memory-efficient than tree-based approaches like retro*)
- Greedily selects routes and simultaneously considers all leaf nodes
- Emphasizes finding backup routes to increase overall success probability

---

## Main Results and Contributions

### Primary Contributions

1. **Novel Formulation:** First to formulate retrosynthesis planning using stochastic processes that explicitly model uncertainty in reaction feasibility and molecule buyability

2. **SSP Metric:** Introduced the Successful Synthesis Probability metric as a principled way to evaluate synthesis plans under uncertainty

3. **Retro-fallback Algorithm:** Proposed a greedy algorithm that directly optimizes SSP, finding effective backup plans

### Experimental Results

- **Benchmark:** Algorithms tested on 500 molecules randomly selected from the GuacaMol test set (drug-like molecules known to be synthesizable)
- **Evaluation:** Primary metric is SSP values estimated with k = 10,000 samples, averaged over 500 molecules
- **Comparisons:** Retro-fallback compared against breadth-first search, retro*, and MCTS (all implemented using the SYNTHESEUS library)

**Key Findings:**
- Retro-fallback generally produces better sets of synthesis plans than MCTS and retro* in terms of SSP
- The SSP of the single best plan is generally similar across all algorithms, suggesting all algorithms find similar "best" plans
- Retro-fallback's advantage comes from finding more effective **backup plans**
- The ability to directly optimize SSP distinguishes retro-fallback from retro*, MCTS, and proof-number search

---

## Limitations

### Conceptual Limitations

1. **No Cost Optimization:** Chemists care about the cost and length of synthesis plans in addition to whether they will work. There is no clear way to incorporate cost considerations directly into either the stochastic process formalism or the retro-fallback algorithm.

2. **No Plan Length/Quality Constraints:** Chemists may care about the length or quality of synthesis plans and may only be willing to consider a limited number of backup plans. These considerations do not fit into the retro-fallback formalism.

3. **Not MILP-based:** Unlike some approaches (e.g., NovoStoic for biosynthesis), retro-fallback does not use Mixed Integer Linear Programming (MILP) optimization. This means it cannot formally optimize over discrete constraints or incorporate complex objective functions.

4. **Organic Reactions Focus:** The evaluation and methodology are focused on organic chemistry reactions and standard drug-like molecule synthesis, limiting applicability to other domains.

5. **Binary Simplification:** The approach collapses nuance into binary outcomes (feasible/infeasible, buyable/not buyable), which may not capture real-world gradations in reaction success probability or molecule availability.

### Practical Limitations

1. **Computational Overhead:** Retro-fallback is slower than other algorithms due to the computational burden of stochastic sampling

2. **Memory Consumption:** Consumes more memory than some newer methods due to the stochastic process computations

3. **Scalability:** May not scale as well as simpler algorithms for very large search spaces

4. **SSP Estimation Challenges:** Stochastic sampling methods are fairly slow for computing SSP, and may fail to discern subtle differences in probability values under specific scenarios

### Future Work Needs

- The most important direction is creating better models of reaction feasibility - without high-quality feasibility models, SSP estimates are not meaningful
- Collaborations with domain experts (chemists) are seen as critical for improving feasibility models

---

## Code Repositories

### Primary Repository (Paper Code)

**GitHub:** [https://github.com/AustinT/retro-fallback-iclr24](https://github.com/AustinT/retro-fallback-iclr24)

**Contents:**
- `retro_fallback_iclr24/`: Core package with retro-fallback implementation and metrics
- `tests/`: Unit tests (pytest compatible)
- `scripts/`: Experimental command generation and plotting utilities
- `official-results/`: Pre-computed experiment data
- `misc/`: Supplementary data files

**Installation:**
```bash
pip install .
```
Note: Manual PyTorch installation may be necessary before pip install.

**Dataset Requirements:**
- eMolecules inventory
- Fusion Retro data
- GuacaMol benchmarks
- RetroStar190 dataset

**License:** MIT

**Status:** Repository frozen for reproducibility; accepts bug-fix PRs only.

### Syntheseus Library (Microsoft)

**GitHub:** [https://github.com/microsoft/syntheseus](https://github.com/microsoft/syntheseus)

Syntheseus is the underlying library used for implementing the search algorithms in the paper.

**Features:**
- Combines search algorithms and reaction models in a standardized way
- Includes implementations of common search algorithms (including retro-fallback)
- Wrappers for state-of-the-art reaction models
- Simple API for custom models and algorithms
- Benchmarking capabilities for retrosynthesis pipelines

**Installation:**
```bash
conda env create -f environment_full.yml
conda activate syntheseus-full
pip install "syntheseus[all]"
```

**Requirements:** Python 3.8+, PyTorch

**License:** MIT

---

## Related Work

- **Retro*:** Earlier A*-based algorithm for retrosynthetic planning (Chen et al., 2020)
- **MCTS:** Monte Carlo Tree Search approaches for retrosynthesis
- **Retro-prob:** Follow-up work proposing a probabilistic model that calculates SSP directly rather than through sampling, claiming improved efficiency
- **Syntheseus paper:** "Re-evaluating Retrosynthesis Algorithms with Syntheseus" (Maziarz et al., 2024) - companion benchmarking work

---

## Acknowledgments

- Austin Tripp: C T Taylor Cambridge International Scholarship, Canadian Centennial Scholarship Fund
- Work partially conducted during internship at Microsoft Research AI4Science
- Contact: {ajt212, jmh233}@cam.ac.uk (Cambridge); {krmaziar, sarahlewis, marwinsegler}@microsoft.com (Microsoft)

---

*Report generated: February 2026*

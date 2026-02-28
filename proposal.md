# Project Proposal: Profit-Maximizing Chemoenzymatic Synthesis Planning via MILP

**600.425/625 Declarative Methods — Spring 2026**
**Student:** Malcolm Krolick
**Date:** February 27, 2026

---

## Problem Statement

Chemical synthesis planning traditionally answers: *"Given a target molecule, what's the cheapest way to make it?"* This is the retrosynthesis problem, addressed by tools like SPARROW [1] using MILP optimization. Separately, minChemBio [2] extends synthesis planning to include enzymatic reactions but only minimizes mode transitions, not economic cost.

I propose a new problem: **"Given available starting materials, market prices, and access to both chemical AND enzymatic reactions, what should I make to maximize profit?"** This requires jointly optimizing:
1. **Product selection** — which molecules to synthesize
2. **Route selection** — which reaction pathways (chemical or enzymatic) to use
3. **Resource allocation** — how much of each starting material to consume

This combines three elements never unified before: (1) profit maximization, (2) joint product/route selection at the molecular level, and (3) chemoenzymatic reaction coverage.

## Proposed Approach

I will formulate this as a Mixed-Integer Linear Program (MILP):

**Variables:**
- $x_p \in \{0,1\}$ — produce product $p$
- $z_r \in \{0,1\}$ — use reaction $r$ (chemical or enzymatic)
- $y_s \in \mathbb{R}^+$ — quantity of starting material $s$ purchased
- $q_p \in \mathbb{R}^+$ — quantity of product $p$ produced
- $t_i \in \{0,1\}$ — chemical↔enzymatic transition at intermediate $i$

**Objective:**
$$\max \sum_p (\text{price}_p \cdot q_p) - \sum_s (\text{cost}_s \cdot y_s) - \sum_r (\text{penalty}_r \cdot z_r) - \lambda \sum_i t_i$$

The transition penalty $\lambda$ captures separation/purification costs when switching between chemical and biological reaction modes.

**Key Constraints:**
- Mass balance at each intermediate node
- Reaction selection implies reactant availability
- Product quantity bounded by reaction yields
- Stoichiometric consistency
- Transition detection at mode boundaries

**Data Sources:**
- Chemical reactions: USPTO (~1.8M reactions)
- Enzymatic reactions: MetaNetX (~57K reactions)
- Pricing: ChemSpace API

## Related Work

| System | Direction | Profit Opt. | Chemoenzymatic | Selects Products |
|--------|:---------:|:-----------:|:--------------:|:----------------:|
| SPARROW [1] | Retro | Cost min. | No | No (fixed targets) |
| minChemBio [2] | Retro | No | Yes | No (fixed targets) |
| Biorefinery MILP [3] | Forward | Yes | No | Yes (plant-level) |
| DESP [4] | Bidirectional | No | No | No (fixed targets) |
| **This work** | **Bidirectional** | **Yes** | **Yes** | **Yes (molecular)** |

**The gap:** Existing retrosynthesis tools (SPARROW, minChemBio) require fixed target molecules. Biorefinery optimization selects products but operates at plant/process level, not molecular reaction level. No existing work combines bidirectional molecular-level synthesis with profit maximization and chemoenzymatic reactions.

## Expected Contributions

1. **Novel MILP formulation** unifying profit optimization, chemoenzymatic synthesis, and product selection
2. **Experimental comparison** against baselines:
   - Greedy: select highest-margin products independently
   - Sequential: select products first, then optimize routes
   - Chemical-only: exclude enzymatic reactions
3. **Analysis** of when enzymatic routes improve profitability
4. **Scalability study** on reaction networks of varying size

## Feasibility & Timeline

- **Weeks 1-2:** Formalize MILP, integrate USPTO + MetaNetX databases
- **Weeks 3-5:** Implement solver (PuLP/OR-Tools), debug on small instances
- **Weeks 6-7:** Run experiments, compare against baselines
- **Week 8:** Write paper, analyze results

The project builds on open-source infrastructure (SPARROW and minChemBio codebases, OR-Tools) and publicly available reaction databases.

## AI Disclosure

I am using Claude Code to assist with literature review, formulation refinement, and code development. All mathematical contributions and experimental design are my own responsibility.

---

**References**

[1] Fromer & Coley. "An algorithmic framework for synthetic cost-aware decision making in molecular design." *Nature Computational Science*, 2024.

[2] Anand et al. "minChemBio: Expanding Chemical Synthesis with Chemo-Enzymatic Pathways Using Minimal Transitions." *ACS Synthetic Biology*, 2025.

[3] "Superstructure-Based Process and Supply Chain Optimization in Sugarcane-Microalgae Biorefineries." *Processes*, 2024.

[4] "Double-Ended Synthesis Planning with Goal-Constrained Bidirectional Search." *arXiv:2407.06334*, 2024.

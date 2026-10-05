# Profit-Maximizing Synthesis Planning: Feasibility Analysis

*Research Report - February 2026*

---

## Your Proposed Idea

**Concept:** Given starting materials of cost X, find what products to make that sell for price Y, maximizing profit (Y - X). This combines:
- **Forward synthesis:** What can I make from these inputs?
- **Retrosynthesis:** How do I get to valuable products?
- **Economic optimization:** Maximize profit margin

---

## What Already Exists

### 1. SPARROW (Coley, 2024) - Retrosynthesis Cost Minimization
- **What it does:** Given target molecules, find cheapest synthesis routes
- **Direction:** Targets → Starting materials (retrosynthesis)
- **Objective:** Minimize cost to make desired molecules
- **Gap:** Does NOT answer "what should I make?"

### 2. Biorefinery Superstructure Optimization (Process Engineering)
- **What it does:** Given biomass feedstock, select products and pathways to maximize profit
- **Direction:** Feedstock → Products (forward)
- **Objective:** Maximize NPV/profit
- **Methods:** MILP superstructure optimization
- **Gap:** Works at **process plant level**, not molecular reaction level

Key papers:
- [Lignin Valorization MILP](https://www.cetjournal.it/index.php/cet/article/view/CET2080039)
- [Biorefinery Superstructure Optimization](https://www.sciencedirect.com/science/article/abs/pii/S0306261924016660)
- [Sugarcane-Microalgae Biorefinery](https://www.mdpi.com/2227-9717/14/2/188)

### 3. Double-Ended Synthesis Planning (DESP, 2024)
- **What it does:** Bidirectional search connecting targets AND starting materials
- **Direction:** Both (forward + retro)
- **Objective:** Find valid routes more efficiently
- **Gap:** Still requires specifying target molecules; no economic optimization

### 4. Chemical Supply Chain MILP
- **What it does:** Optimize chemical production/distribution networks
- **Direction:** Forward (planning level)
- **Objective:** Maximize profit across supply chain
- **Gap:** Works at facility/logistics level, not molecular synthesis level

---

## The Gap You've Identified

**Nobody has combined:**

| Component | Exists Where? |
|-----------|---------------|
| Molecular-level forward synthesis prediction | ASKCOS forward predictor, neural models |
| Molecular-level retrosynthesis | SPARROW, ASKCOS, many tools |
| Economic cost modeling at molecular level | SPARROW (cost), ChemSpace API |
| Product value/pricing data | ChemSpace, eMolecules, Sigma-Aldrich |
| **MILP for: "Given cheap inputs, find profitable outputs"** | **NOT DONE at molecular level** |

### The Novel Problem Formulation

```
Given:
  - Set of available starting materials S with costs c_s
  - Universe of possible products P with selling prices p_i
  - Reaction network R connecting S to P

Find:
  - Which products to make
  - Which synthesis routes to use

Maximize:
  Σ (price_i × quantity_i) - Σ (cost_s × amount_used_s) - reaction_costs

Subject to:
  - Reaction feasibility constraints
  - Mass balance
  - Capacity constraints (optional)
```

---

## Why This IS Novel for Declarative Methods

### Novelty Assessment

| Aspect | Existing Work | Your Contribution |
|--------|---------------|-------------------|
| Problem direction | Retro only (SPARROW) or process-level forward (biorefinery) | Molecular-level bidirectional |
| Objective | Cost minimization OR route finding | Profit maximization |
| Decision | Which routes for fixed targets | Which targets AND which routes |
| Scale | Single molecule/batch OR plant-level | Molecular network level |

### What Makes It Interesting for Declarative Methods

1. **Novel MILP formulation:** The "what to make" decision combined with "how to make it" creates a new problem structure

2. **Interesting constraints:**
   - Forward synthesis feasibility (reaction rules)
   - Stoichiometric mass balance
   - Shared intermediate accounting (like SPARROW)
   - Market constraints (demand limits)

3. **Clear comparison opportunities:**
   - Your MILP vs. greedy product selection
   - Different encoding strategies
   - Scalability analysis

---

## Concrete Project Formulation

### The Problem: Chemical Arbitrage Optimization

**Input:**
- Catalog of buyable chemicals with prices (ChemSpace API)
- Catalog of sellable chemicals with prices (same source, or Sigma-Aldrich)
- Reaction database (USPTO or ASKCOS rules)

**Output:**
- Which chemicals to buy
- Which chemicals to sell
- Synthesis network connecting them
- Expected profit

### MILP Formulation Sketch

```
Variables:
  x_i ∈ {0,1}     - produce product i
  y_s ∈ ℝ+        - amount of starting material s purchased
  z_r ∈ {0,1}     - use reaction r
  q_i ∈ ℝ+        - quantity of product i produced

Objective:
  max Σ_i (price_i × q_i) - Σ_s (cost_s × y_s) - Σ_r (reaction_cost_r × z_r)

Constraints:
  - Mass balance at each intermediate
  - Reaction selection implies reactant availability
  - Product quantity limited by reaction yields
  - Optional: demand constraints, capacity constraints
```

### Data Sources

| Data | Source | Availability |
|------|--------|--------------|
| Chemical prices (buy) | ChemSpace API | Requires API key |
| Chemical prices (sell) | Sigma-Aldrich, ChemSpace | Public/API |
| Reactions | USPTO (1.8M), ASKCOS templates | Public |
| Reaction yields | USPTO metadata, ASKCOS | Partial |

### Feasibility Assessment

| Factor | Assessment |
|--------|------------|
| Data availability | **HIGH** - all sources exist |
| MILP complexity | **MEDIUM** - similar to SPARROW but bidirectional |
| Implementation effort | **MEDIUM** - can reuse SPARROW code structure |
| Novelty | **HIGH** - no existing molecular-level profit optimization |
| Declarative methods depth | **HIGH** - novel formulation, clear constraints |

---

## Comparison to Original Retrosynthesis Idea

| Aspect | Original Idea | New Profit-Maximization Idea |
|--------|---------------|------------------------------|
| MILP formulation | Already done (SPARROW) | Novel bidirectional formulation |
| Enzymatic extension | Data integration work | Still applicable as extension |
| Problem novelty | Low (incremental) | High (new problem class) |
| Declarative contribution | Weak | Strong |
| Publication potential | Low | Medium-High |

---

## Risks and Mitigations

### Risk 1: Reaction Yield Data Quality
- **Issue:** USPTO doesn't always have yields
- **Mitigation:** Use conservative estimates, sensitivity analysis

### Risk 2: Price Data Staleness
- **Issue:** Chemical prices fluctuate
- **Mitigation:** Focus on relative comparisons, not absolute profits

### Risk 3: Scalability
- **Issue:** Large reaction networks may be intractable
- **Mitigation:** Start with subnetwork (e.g., specific chemical family)

### Risk 4: Forward Synthesis Quality
- **Issue:** Forward prediction less mature than retrosynthesis
- **Mitigation:** Use bidirectional approach, validate with known routes

---

## Recommended Project Scope

### Minimum Viable Project

1. **Subset the problem:**
   - Pick a chemical family (e.g., commodity aromatics, or pharma intermediates)
   - ~100-1000 chemicals, ~1000-10000 reactions

2. **Build the MILP:**
   - Binary product selection
   - Route selection
   - Mass balance constraints
   - Profit objective

3. **Compare against baselines:**
   - Greedy: pick highest-margin products independently
   - SPARROW-style: pick products then optimize routes separately

4. **Analyze:**
   - When does joint optimization beat greedy?
   - Scalability characteristics
   - Sensitivity to price changes

### Ambitious Extensions

- Add enzymatic reactions (your original chemoenzymatic interest)
- Add uncertainty in prices (stochastic MILP)
- Add capacity constraints (make it more realistic)

---

## Verdict

**YES, this reformulation creates genuine novelty.**

The key insight is that existing work either:
- Optimizes routes for **fixed targets** (SPARROW), or
- Optimizes product selection at **plant/process level** (biorefinery MILP)

Nobody has formulated **molecular-level profit maximization** where both product selection AND route selection are jointly optimized.

This is a legitimate declarative methods contribution because:
1. Novel problem formulation requiring new MILP structure
2. Clear constraints with interesting interactions
3. Comparison opportunities (joint vs. sequential optimization)
4. Scalability challenges typical of declarative methods research

---

## Next Steps

1. Confirm the gap with a few more targeted searches
2. Sketch the full MILP formulation mathematically
3. Identify a concrete chemical domain to test on
4. Discuss with Prof. Eisner before the proposal deadline

---

*Report generated: February 27, 2026*

## Sources

- [SPARROW Paper](https://www.nature.com/articles/s43588-024-00639-y)
- [Double-Ended Synthesis Planning](https://arxiv.org/pdf/2407.06334)
- [Lignin Valorization MILP](https://www.cetjournal.it/index.php/cet/article/view/CET2080039)
- [Biorefinery Superstructure Optimization](https://www.mdpi.com/2227-9717/14/2/188)
- [Chemical Supply Chain MILP](https://link.springer.com/article/10.1007/s00291-002-0102-6)
- [minChemBio](https://pubs.acs.org/doi/10.1021/acssynbio.4c00692)

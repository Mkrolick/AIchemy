# AIchemy: Project Work Breakdown

## Project Overview

**Objective:** Build the first unified MILP retrosynthesis framework that combines all four critical elements:
1. MILP-based retrosynthesis optimization
2. Chemoenzymatic reaction coverage (both chemical and enzymatic)
3. Real cost modeling (starting materials + enzyme procurement)
4. Sensitivity analysis on enzyme confidence/feasibility

**Gap Being Addressed:** No published system combines all four elements as of February 2026. The closest systems each deliver two or three requirements:

| System | MILP | Chemoenzymatic | Cost Modeling | Sensitivity Analysis |
|--------|:----:|:--------------:|:-------------:|:--------------------:|
| SPARROW (2024) | Yes | No | Yes (ChemSpace API) | Yes (lambda-weights) |
| minChemBio (2025) | Yes | Yes | No (transition proxy) | No |
| Gao et al. (2020) | Yes | No | No (inventory count) | Yes (Pareto front) |
| Retro-fallback (2024) | No (Greedy) | No | No | Yes (SSP stochastic) |

---

## Work Packages

### WP1: Database Integration & Preprocessing

**Goal:** Create a unified reaction database spanning chemical and enzymatic transformations with standardized atom mapping.

#### Tasks

- [ ] **1.1 Chemical Reaction Database Setup**
  - Source: USPTO (~1.8M reactions, 1.2M molecules)
  - Preprocessing pipeline from minChemBio
  - Extract one-to-one mappings using Tanimoto similarity
  - Final target: ~1.1M chemical reaction mappings

- [ ] **1.2 Enzymatic Reaction Database Setup**
  - Source: MetaNetX (~57,500 reactions)
  - Preprocessing: Remove cofactors (CO2, H2O, ATP, NAD+, etc.)
  - Support bidirectional reactions
  - Final target: ~67,600 enzymatic mappings

- [ ] **1.3 Unified Database Schema**
  - Design common schema for chemical and enzymatic reactions
  - Standardize molecule identifiers (SMILES, InChI)
  - Create reaction type annotations (chemical/enzymatic)
  - Implement reaction reversibility flags

- [ ] **1.4 Atom Mapping Standardization**
  - Integrate RXNMapper or equivalent for consistent atom mapping
  - Handle multi-substrate reactions with Tanimoto-based primary mapping
  - Quality validation pipeline for mapping accuracy

#### Deliverables
- Unified reaction database (JSON/SQL format)
- Preprocessing scripts for both USPTO and MetaNetX
- Data quality report with coverage statistics

---

### WP2: Cost Modeling Infrastructure

**Goal:** Build comprehensive cost model incorporating reagent/starting material prices plus enzyme production/procurement costs.

#### Tasks

- [ ] **2.1 Chemical Cost Integration**
  - Integrate ChemSpace API (following SPARROW approach)
  - Alternative: eMolecules pricing database
  - Implement buyability determination logic
  - Create "buy vs. synthesize" decision nodes

- [ ] **2.2 Enzyme Cost Modeling**
  - Research enzyme procurement cost sources:
    - Commercial enzyme suppliers (Sigma-Aldrich, NEB)
    - Recombinant expression cost estimates
    - Enzyme stability/reusability factors
  - Create enzyme cost database with confidence intervals

- [ ] **2.3 Cost Normalization Framework**
  - Normalize costs across different units ($/g, $/unit activity)
  - Handle currency conversions and date-based pricing
  - Implement cost caching with TTL for API calls

- [ ] **2.4 Transition Cost Estimation**
  - Model separation/purification costs at chemical-biological transitions
  - Estimate solvent exchange costs
  - Factor in scale-dependent cost variations

#### Deliverables
- Chemical cost API integration module
- Enzyme cost database with documentation
- Cost normalization utilities
- Cost update/refresh automation scripts

---

### WP3: MILP Formulation & Solver Integration

**Goal:** Develop the core MILP formulation with reaction selection as binary variables and a cost-based objective.

#### Tasks

- [ ] **3.1 Decision Variable Definition**
  - Binary variables for reaction selection (following SPARROW structure)
  - Binary variables for molecule inclusion
  - Binary variables for chemical-biological transition tracking (from minChemBio)

- [ ] **3.2 Objective Function Design**
  - Multi-term objective with tunable weights:
    ```
    minimize: lambda_1 * (starting material costs)
            + lambda_2 * (enzyme costs)
            + lambda_3 * (transition penalties)
            - lambda_4 * (pathway confidence scores)
    ```
  - Support for alternative formulations (e.g., epsilon-constraint method)

- [ ] **3.3 Constraint Implementation**
  - Reactant availability constraints
  - Product synthesis constraints (at least one producing reaction)
  - Cycle prevention constraints
  - Mass balance constraints for intermediates
  - Thermodynamic consistency constraints (no bidirectional conflicts)

- [ ] **3.4 Solver Integration**
  - Primary: CPLEX/Gurobi for production use
  - Fallback: CBC (open-source, via PuLP)
  - Solver configuration optimization
  - Solution enumeration for alternative pathways

- [ ] **3.5 Performance Optimization**
  - Implement warm-start capabilities
  - Add branching priorities for key variables
  - Develop problem decomposition strategies for large instances

#### Deliverables
- MILP model implementation (PuLP/Pyomo compatible)
- Solver configuration documentation
- Benchmark results on test cases

---

### WP4: Confidence & Feasibility Scoring

**Goal:** Implement reaction confidence scoring and enzyme feasibility prediction for both chemical and enzymatic steps.

#### Tasks

- [ ] **4.1 Chemical Reaction Scoring**
  - Integrate ASKCOS forward predictor for chemical reactions
  - Alternative: Train custom forward prediction model
  - Calibrate scores to empirical success rates

- [ ] **4.2 Enzyme Feasibility Scoring**
  - Integrate EnzRank from novoStoic 2.0 for enzyme-substrate compatibility
  - Incorporate thermodynamic feasibility via dGPredictor
  - Model enzyme promiscuity/substrate scope uncertainty

- [ ] **4.3 Unified Confidence Framework**
  - Normalize confidence scores across reaction types (0-1 scale)
  - Handle different uncertainty sources:
    - Reaction mechanism uncertainty
    - Enzyme activity predictions
    - Thermodynamic feasibility
  - Implement confidence aggregation for multi-step pathways

- [ ] **4.4 Confidence Calibration**
  - Collect ground-truth data from literature
  - Calibrate predicted probabilities to empirical outcomes
  - Implement cross-validation framework

#### Deliverables
- Unified confidence scoring module
- Calibration datasets and methodology
- Documentation of score interpretation

---

### WP5: Sensitivity Analysis Framework

**Goal:** Enable parametric sensitivity analysis and/or stochastic programming formulation for enzyme feasibility.

#### Tasks

- [ ] **5.1 Parametric Sensitivity Implementation**
  - Implement lambda-weight variation (following Gao et al.)
  - Automated Pareto front generation
  - Enzyme confidence threshold variation studies

- [ ] **5.2 Stochastic Programming Extension**
  - Scenario-based enzyme feasibility modeling
  - Two-stage stochastic MILP formulation:
    - Stage 1: Route selection under uncertainty
    - Stage 2: Recourse actions when reactions fail
  - Sample average approximation (SAA) implementation

- [ ] **5.3 Robust Optimization Alternative**
  - Implement uncertainty sets for enzyme confidence
  - Worst-case optimization formulation
  - Trade-off analysis: robustness vs. expected cost

- [ ] **5.4 Visualization & Reporting**
  - Pareto front visualization tools
  - Sensitivity tornado charts
  - Confidence interval reporting for optimal solutions

#### Deliverables
- Sensitivity analysis module
- Pareto front visualization dashboard
- Technical report on stochastic extensions

---

### WP6: Retrosynthesis Engine Integration

**Goal:** Connect the MILP optimizer with retrosynthetic tree search for route generation.

#### Tasks

- [ ] **6.1 Chemical Retrosynthesis Integration**
  - ASKCOS API integration (tree builder, condition recommender)
  - Alternative: Custom template-based expansion
  - Configure search parameters (depth, time limits, expansion counts)

- [ ] **6.2 Enzymatic Retrosynthesis Integration**
  - Integrate enzymatic templates from Levin et al. (7,984 templates)
  - Alternative: MetaNetX-based enzymatic expansion
  - Handle enzyme-specific constraints (cofactor requirements, pH, temperature)

- [ ] **6.3 Unified Tree Builder**
  - Merge chemical and enzymatic expansion modules
  - Implement hybrid search strategy:
    - Option A: Interleaved expansion
    - Option B: Separate trees with post-hoc merging
  - Manage search space explosion

- [ ] **6.4 Route Graph Construction**
  - Build unified RouteGraph structure (SPARROW-style)
  - Annotate nodes with cost and confidence data
  - Implement efficient graph traversal algorithms

#### Deliverables
- Retrosynthesis engine with chemoenzymatic support
- RouteGraph data structure and utilities
- Integration tests with benchmark molecules

---

### WP7: User Interface & Workflow

**Goal:** Create accessible interfaces for chemists and researchers.

#### Tasks

- [ ] **7.1 Command-Line Interface**
  - SPARROW-style CLI with target SMILES input
  - Configuration file support for complex runs
  - Progress reporting and logging

- [ ] **7.2 Web Interface (Optional)**
  - Streamlit-based interface (following minChemBio)
  - Route visualization with interactive graphs
  - Cost breakdown displays

- [ ] **7.3 Output Formats**
  - JSON route specifications
  - Human-readable pathway summaries
  - Export to synthesis planning tools (Synthia, ChemDraw)

- [ ] **7.4 Documentation**
  - User guide with tutorials
  - API documentation
  - Troubleshooting guide

#### Deliverables
- CLI application
- Optional web interface
- Comprehensive documentation

---

### WP8: Validation & Case Studies

**Goal:** Validate the framework on industrially relevant targets and compare against existing tools.

#### Tasks

- [ ] **8.1 Benchmark Dataset Curation**
  - Select 50-100 target molecules spanning:
    - Pharmaceutical intermediates
    - Bioplastic precursors (FDCA, TPA)
    - Natural product analogs
    - Chiral building blocks

- [ ] **8.2 Comparison Studies**
  - Run SPARROW on same targets (chemical-only baseline)
  - Run minChemBio on same targets (transition-minimization baseline)
  - Run ASKCOS standalone for route quality comparison

- [ ] **8.3 Case Study: FDCA Synthesis**
  - Full analysis of 2,5-furandicarboxylic acid routes
  - Compare with minChemBio published results
  - Cost-sensitivity analysis with real pricing data

- [ ] **8.4 Case Study: Pharmaceutical Target**
  - Select WHO essential medicine target
  - Full chemoenzymatic route exploration
  - Comparison with published synthetic routes

- [ ] **8.5 Computational Performance Evaluation**
  - Scalability testing (10, 50, 100, 500 targets)
  - Memory profiling
  - Solver performance comparison (CPLEX vs. CBC)

#### Deliverables
- Benchmark dataset with ground truth
- Comparison analysis report
- Case study publications/reports

---

## Technical Architecture

```
+------------------+     +------------------+     +------------------+
|   Reaction DBs   |     |    Cost APIs     |     | Confidence      |
|  - USPTO         |     |  - ChemSpace     |     | Scoring         |
|  - MetaNetX      |     |  - Enzyme costs  |     |  - ASKCOS       |
+--------+---------+     +--------+---------+     |  - EnzRank      |
         |                        |               |  - dGPredictor  |
         v                        v               +--------+---------+
+--------+---------+     +--------+---------+              |
|  Retrosynthesis  |---->|   Route Graph    |<-------------+
|  Engine          |     |   Construction   |
|  - Chemical      |     +--------+---------+
|  - Enzymatic     |              |
+------------------+              v
                        +--------+---------+
                        |   MILP Solver    |
                        |  - Objective     |
                        |  - Constraints   |
                        +--------+---------+
                                 |
                        +--------v---------+
                        |   Sensitivity    |
                        |   Analysis       |
                        |  - Pareto front  |
                        |  - Stochastic    |
                        +--------+---------+
                                 |
                        +--------v---------+
                        |   Output &       |
                        |   Visualization  |
                        +------------------+
```

---

## Dependencies & Tools

### Core Dependencies
- **Python 3.11+**
- **RDKit** - Chemistry toolkit
- **PuLP/Pyomo** - MILP modeling
- **CPLEX/Gurobi** - Commercial solvers (optional: CBC as fallback)
- **NetworkX** - Graph algorithms
- **Pandas/NumPy** - Data handling

### External Services/APIs
- **ASKCOS** - Retrosynthesis engine
- **ChemSpace API** - Chemical pricing
- **dGPredictor** - Thermodynamic feasibility

### Visualization
- **Matplotlib/Plotly** - Charts and plots
- **Streamlit** - Web interface (optional)

---

## Risk Factors & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Enzyme cost data unavailable | High | Medium | Build estimation model from literature values; use confidence bounds |
| ASKCOS API rate limits | Medium | Low | Implement caching; local ASKCOS deployment option |
| MILP scalability issues | High | Medium | Problem decomposition; heuristic pre-filtering of routes |
| Enzyme-substrate prediction accuracy | High | High | Conservative confidence intervals; ensemble methods; experimental validation |
| Integration complexity | Medium | High | Modular architecture; extensive testing; incremental integration |

---

## References

### Key Papers to Build Upon
1. Fromer & Coley (2024) - SPARROW: Cost-aware MILP framework
2. Anand, Upadhyay & Maranas (2025) - minChemBio: Chemoenzymatic MILP
3. Gao et al. (2020) - Multi-objective MILP with Pareto analysis
4. Tripp et al. (2024) - Retro-fallback: Stochastic feasibility modeling
5. Levin et al. (2022) - ASKCOS enzymatic extensions

### Code Repositories
- SPARROW: https://github.com/coleygroup/sparrow
- minChemBio: https://github.com/maranasgroup/chemo-enz
- Combined synthesis planning: https://github.com/Coughy1991/Combined_synthesis_planning
- Retro-fallback: https://github.com/AustinT/retro-fallback-iclr24

---

## Success Metrics

1. **Coverage:** Successfully plan routes for >80% of benchmark targets
2. **Cost Improvement:** Demonstrate >15% cost reduction vs. chemical-only planning on chemoenzymatic-amenable targets
3. **Scalability:** Handle 100+ target molecules in <24 hours compute time
4. **Validation:** Match or improve upon literature routes for case study targets
5. **Usability:** Provide working CLI and documentation for external users

---

*Document generated: February 2026*
*Project: AIchemy - Unified Chemoenzymatic MILP Retrosynthesis Framework*

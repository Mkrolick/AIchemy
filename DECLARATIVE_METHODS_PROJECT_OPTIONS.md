# Declarative Methods Project Options

*Research Report - February 2026*
*For 600.425/625 Declarative Methods (Prof. Eisner)*

---

## Executive Summary

After extensive research, I identified **5 promising project directions** with genuine novelty for a declarative methods class project. These are ranked by feasibility and novelty trade-off.

**Top Recommendation:** Option 1 (LLM Inference Scheduling via CSP) or Option 3 (MaxSAT for Sparse Attention Pattern Discovery) offer the best balance of novelty, feasibility, and declarative methods depth.

---

## Option 1: LLM Inference Scheduling as Constraint Satisfaction

### The Gap
Recent work ([ExeGPT](https://arxiv.org/pdf/2404.07947), [InferMax](https://arxiv.org/html/2504.11320v2)) formulates LLM inference scheduling as optimization problems, but:
- ExeGPT uses branch-and-bound heuristics
- InferMax mentions CSP formulation but doesn't fully explore it
- Nobody has systematically compared CP-SAT vs. MILP vs. heuristic approaches

### The Problem
Given batches of LLM requests with varying input/output lengths, schedule them to maximize throughput subject to:
- GPU memory constraints (KV cache grows dynamically)
- Latency SLOs (service level objectives)
- Preemption/eviction costs

### Why It's Novel
- The dynamic memory growth makes this different from classical job shop scheduling
- KV cache constraints create interesting propagation opportunities
- Direct comparison of declarative approaches (CP-SAT, MILP) vs. current heuristics

### Deliverables
1. CP-SAT formulation using OR-Tools
2. MILP formulation using Gurobi/CPLEX
3. Comparison against ScheduleMax/vLLM heuristics
4. Analysis of when declarative methods win/lose

### Feasibility: HIGH
- Simulatable without real GPUs (use latency models from papers)
- Clear benchmarks exist (request traces from papers)
- OR-Tools CP-SAT is excellent for scheduling

### Category Fit
Category 4 (comparison) + Category 1 (real-world problem)

### Key References
- [ExeGPT: Constraint-Aware Resource Scheduling](https://dl.acm.org/doi/10.1145/3620665.3640383)
- [Online Scheduling with KV Cache Constraints](https://arxiv.org/html/2502.07115)
- [Fluid-Guided Online Scheduling](https://arxiv.org/html/2504.11320v2)

---

## Option 2: DNA Sequence Design via MaxSAT

### The Gap
DNA sequence design for synthetic biology requires satisfying multiple constraints:
- Avoid secondary structures (hairpins)
- Avoid homology to host genome
- Meet GC content requirements
- Avoid restriction sites
- Maintain codon optimization

Current tools (R2oDNA Designer, etc.) use Monte Carlo/simulated annealing. **No published work uses MaxSAT/SAT for DNA sequence design.**

### The Problem
Given constraints on a DNA sequence:
- Hard constraints: no restriction sites, valid codons
- Soft constraints: GC content preferences, codon frequency optimization

Formulate as Weighted Partial MaxSAT and compare against stochastic methods.

### Why It's Novel
- SAT/MaxSAT unexplored in this domain (confirmed by search)
- Natural fit: sequence design is highly constrained combinatorial problem
- Could discover whether declarative methods outperform Monte Carlo

### Deliverables
1. MaxSAT encoding of DNA sequence constraints
2. Implementation using RC2 or Open-WBO solver
3. Benchmark against existing tools (R2oDNA, DNA Chisel)
4. Analysis of constraint structure exploitability

### Feasibility: MEDIUM-HIGH
- Clear constraint definitions from biology literature
- MaxSAT solvers are mature
- May need to consult with biology students for realistic constraints

### Category Fit
Category 1 (real-world problem) + Category 4 (comparison to existing methods)

### Key References
- [R2oDNA Designer](https://pubs.acs.org/doi/10.1021/sb4001323)
- [DNA Coding Design Constraints](https://pmc.ncbi.nlm.nih.gov/articles/PMC9407506/)
- [Genetic Design via Combinatorial Constraint Specification](https://pubs.acs.org/doi/10.1021/acssynbio.7b00154)

---

## Option 3: MaxSAT for Sparse Attention Pattern Discovery

### The Gap
Transformer attention sparsity is a hot topic. Current approaches:
- Fixed patterns (Longformer, BigBird): hand-designed, may not fit data
- Learned patterns (Reformer): gradient-based, computationally expensive
- **Nobody uses combinatorial optimization to find optimal sparse patterns**

### The Problem
Given a pretrained attention matrix (or distribution over attention patterns):
- Find a sparse pattern (k connections per query) that maximizes preserved attention mass
- Subject to structural constraints (e.g., must include local window, global tokens)

This is a combinatorial optimization problem: select k edges per row from attention graph.

### Why It's Novel
- Attention sparsity research uses ML/heuristics, not declarative optimization
- MaxSAT can encode "maximize attention preserved subject to sparsity budget"
- Could provide theoretical baselines for learned methods

### Deliverables
1. MaxSAT formulation for attention sparsity pattern selection
2. Comparison: optimal patterns vs. fixed patterns (Longformer) vs. learned (Reformer)
3. Analysis: how far from optimal are heuristic methods?
4. Scalability analysis

### Feasibility: MEDIUM
- Need pretrained attention matrices (available from HuggingFace models)
- MaxSAT encoding is non-trivial but doable
- May face scalability issues for large attention matrices

### Category Fit
Category 1 (novel application) + Category 4 (comparison to heuristics)

### Key References
- [Sparse Attention Post-Training](https://arxiv.org/html/2512.05865)
- [Crisp Attention: Structured Sparsity](https://arxiv.org/html/2508.06016v1)
- [The Sparse Frontier](https://arxiv.org/pdf/2504.17768)

---

## Option 4: A Little Language for Constraint Model Specification

### The Gap
LLMs are being used to generate constraint models from natural language ([DCP-Bench](https://arxiv.org/html/2506.06052), [ACMG](https://www.mdpi.com/2076-3417/15/12/6518)), but:
- They generate MiniZinc/Pyomo code directly (error-prone)
- No intermediate representation exists for constraint model structure
- Hard to verify correctness of generated models

### The Problem
Design a "little language" that:
1. Captures constraint model structure declaratively
2. Is easier for LLMs to generate correctly than full MiniZinc
3. Compiles to multiple backends (MiniZinc, OR-Tools, Gurobi)
4. Enables structural verification before solving

### Why It's Novel
- Fills gap between natural language and solver-specific syntax
- Could improve LLM-generated constraint model accuracy
- Language design + solver mapping is core declarative methods

### Deliverables
1. Grammar specification for the little language
2. Compiler to at least 2 backends (MiniZinc + OR-Tools)
3. Evaluation: LLM accuracy generating little language vs. MiniZinc directly
4. Structural verification rules

### Feasibility: MEDIUM
- Language design requires careful thought
- Compiler implementation is substantial work
- LLM evaluation adds complexity

### Category Fit
Category 5 (little language design)

### Key References
- [Constraint Modelling with LLMs](https://drops.dagstuhl.de/storage/00lipics/lipics-vol307-cp2024/LIPIcs.CP.2024.20/LIPIcs.CP.2024.20.pdf)
- [Do LLMs Understand Constraint Programming?](https://satcpdp25.github.io/submissions/satcpdp-25_paper_24.pdf)
- [DCP-Bench](https://arxiv.org/html/2506.06052)

---

## Option 5: CP-SAT vs. MILP for GPU Kernel Scheduling

### The Gap
Deep learning workload scheduling on GPUs uses MILP ([Chronus](https://dl.acm.org/doi/full/10.1145/3638757), [MixTran](https://www.mdpi.com/1999-4893/18/7/385)), but:
- CP-SAT has dominated scheduling benchmarks since 2018
- No systematic comparison of CP-SAT vs. MILP for GPU workload scheduling
- Novel constraints (memory growth, tensor parallelism) may favor one approach

### The Problem
Given deep learning jobs with:
- GPU memory requirements
- Precedence constraints (data dependencies)
- Tensor parallelism options

Schedule to minimize makespan or maximize throughput.

### Why It's Novel
- CP-SAT unexplored for this specific problem structure
- GPU-specific constraints (memory bandwidth, NVLink) create interesting propagation opportunities
- Could establish which declarative paradigm fits better

### Deliverables
1. CP-SAT formulation using OR-Tools
2. MILP formulation using Gurobi
3. Benchmark on DL workload traces
4. Analysis of problem structure and solver performance

### Feasibility: HIGH
- Clear problem definition
- Workload traces available from papers
- Both OR-Tools and Gurobi are accessible

### Category Fit
Category 4 (comparison)

### Key References
- [Deep Learning Workload Scheduling Survey](https://dl.acm.org/doi/full/10.1145/3638757)
- [PyJobShop](https://arxiv.org/pdf/2502.13483)
- [Chronus](https://dl.acm.org/doi/full/10.1145/3638757)

---

## Comparison Matrix

| Option | Novelty | Feasibility | Declarative Depth | Publication Potential |
|--------|---------|-------------|-------------------|----------------------|
| 1. LLM Inference Scheduling | High | High | High | Medium-High |
| 2. DNA Sequence MaxSAT | Very High | Medium-High | High | High |
| 3. Sparse Attention MaxSAT | Very High | Medium | Medium-High | High |
| 4. Little Language for CM | High | Medium | Very High | Medium |
| 5. GPU Scheduling CP vs MILP | Medium | High | High | Medium |

---

## Recommendation

**For maximum novelty + feasibility:** Option 1 (LLM Inference Scheduling) or Option 2 (DNA Sequence MaxSAT)

**For Eisner's "little language" interest:** Option 4

**For pure comparison study:** Option 5 (GPU Scheduling)

**For ML/AI focus:** Option 3 (Sparse Attention)

---

## Why NOT the Original Retrosynthesis Idea

The original AIchemy project (chemoenzymatic MILP retrosynthesis) fails because:
1. MILP for retrosynthesis is already well-established (SPARROW, minChemBio, Gao et al.)
2. Adding enzymatic reactions is data integration, not declarative methods novelty
3. Stochastic extensions are awkward to model (sequential reaction execution)
4. The "contribution" would be engineering, not declarative methods insight

The options above offer clearer declarative methods contributions with less prior work to compete against.

---

## Next Steps

1. Pick 1-2 options that interest you
2. Do a quick literature check to confirm the gap still exists
3. Sketch the constraint formulation
4. Discuss with Prof. Eisner before the proposal deadline

---

*Report generated: February 27, 2026*

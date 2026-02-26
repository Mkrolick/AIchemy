# The four-part MILP retrosynthesis framework nobody has built yet

**No published system combines all four elements — MILP-based retrosynthesis, chemoenzymatic reaction coverage, real cost modeling, and sensitivity analysis on enzyme confidence — as of February 2026.** This represents a well-defined gap at the intersection of mathematical optimization, biocatalysis planning, and decision-making under uncertainty. The closest individual systems each deliver two or three of the four requirements, and together they prove every component is technically feasible. What's missing is their integration into a single framework.

The field has advanced rapidly on separate fronts: MILP for retrosynthesis is mature (at least six systems), chemoenzymatic planning tools proliferated in 2024–2025 (at least seven platforms), and stochastic treatment of reaction feasibility appeared at ICLR 2024. But these three streams of work have not converged.

## SPARROW comes closest at three out of four

SPARROW (Fromer & Coley, *Nature Computational Science*, 2024) is the single system that satisfies the most criteria. It uses a **MILP formulation** (PuLP/Gurobi solvers) to simultaneously select molecules and synthetic routes for drug discovery campaigns, pulling **real pricing data from the ChemSpace API** for starting materials. Its objective function balances expected information gain against synthetic cost via tunable λ-weights controlling the trade-off between molecule utility, starting material price, and **reaction confidence scores** from ASKCOS's forward predictor. Varying these weights — or using the built-in Bayesian optimization (`--bayes-iters`) to tune them automatically — constitutes a form of sensitivity analysis on how reaction feasibility assumptions shift route selection.

Where SPARROW falls short is enzymatic reactions. It relies entirely on ASKCOS's ~163,000 organic chemistry templates from Reaxys/USPTO. There is no integration of biocatalytic transformations, enzyme databases, or any mechanism to incorporate enzymatic steps. SPARROW is built for medicinal chemistry, not chemoenzymatic synthesis.

## minChemBio is the only MILP system with chemoenzymatic scope

minChemBio (Anand, Upadhyay & Maranas, *ACS Synthetic Biology*, 2025) is the only published tool that combines a **MILP formulation** with **both chemical and enzymatic reactions** in a unified search. It draws on **~1.8 million chemical reactions from USPTO** and **~57,500 enzymatic reactions from MetaNetX**, tracking the main carbon path via Tanimoto similarity and solving a MILP to find connected pathways from source to target. Its demonstrated case studies include 2,5-furandicarboxylic acid and terephthalate — molecules where hybrid routes offer genuine advantages.

However, minChemBio's objective function **minimizes the number of transitions between chemical and biological reaction modes** (a proxy for separation/purification burden), not actual dollar costs. It uses no pricing databases, no reagent cost data, and no enzyme procurement cost estimates. It also performs **no sensitivity analysis** of any kind — thermodynamic feasibility is assessed post-hoc via dGPredictor, but there is no parametric exploration of how reaction confidence or enzyme reliability affects route optimality.

## The Gao–Jensen MIT papers pioneered MILP sensitivity on confidence

Gao et al. (*Reaction Chemistry & Engineering*, 2020) and the follow-up Gao et al. (*JCIM*, 2021) from MIT established the template for MILP-based retrosynthesis with explicit confidence trade-offs. The 2020 paper formulates a **multi-objective MILP** (solved with CPLEX) to select synthesis routes for 99 WHO essential medicines, minimizing chemical inventory while maximizing pathway feasibility scores. It systematically **varies a weighting parameter λ from 0 to 1** to trace the Pareto front between inventory minimization and reaction confidence, and explores a stricter scenario that excludes all low-score reactions entirely. This is the clearest published example of sensitivity analysis on reaction confidence in a MILP retrosynthesis context.

The limitation is twofold: these papers optimize **inventory count** (number of unique chemicals), not monetary cost — they explicitly state "we did not use the price of the chemicals" — and they use only organic chemistry templates from ASKCOS with **no enzymatic reactions**.

## Other systems fill individual niches but not the full combination

Several other systems contribute relevant pieces:

- **novoStoic / novoStoic 2.0** (Maranas group, *Nature Communications* 2018; *PLoS Computational Biology* 2025) uses MILP for biosynthetic pathway design with enzymatic reactions and novel putative enzymatic steps. novoStoic 2.0 adds EnzRank for enzyme-substrate compatibility scoring. But it handles **enzymatic reactions only** (no chemical synthesis steps), uses no pricing data in the pathway MILP (optStoic can theoretically optimize price efficiency at the stoichiometry scoping level), and performs no sensitivity analysis on confidence.

- **Retro-fallback** (Tripp et al., *ICLR 2024*) is the most sophisticated treatment of uncertainty in retrosynthesis, modeling reaction feasibility and molecule buyability as stochastic processes with correlated outcomes and defining a "Successful Synthesis Probability" metric. But it uses a greedy algorithm, **not MILP**, includes no cost optimization, and handles only organic reactions.

- **ASKCOS with enzymatic extensions** (Levin et al., *Nature Communications* 2022) integrates 7,984 enzymatic templates alongside 163,723 chemical templates in a hybrid tree search. It maintains a buyable-compounds database with approximate prices. But its search engine is MCTS/Retro*, **not MILP**, and it performs no formal sensitivity analysis.

- **ChemEnzyRetroPlanner** (*Nature Communications*, 2025), **BioNavi** (*JACS Au*, 2024), **ACERetro/SPScore** (*Digital Discovery*, 2025), and **TTLAB** (Kreutter & Reymond, *Chemical Science*, 2024) all provide chemoenzymatic planning but use neural network-guided tree search, not mathematical programming. None incorporate cost data or sensitivity analysis.

- **RetSynth** (Whitmore et al., *PLoS Computational Biology*, 2020) and **BNICE.ch** use integer programming for biological pathway design, but neither includes chemical reactions, cost modeling, or sensitivity analysis.

## A clear gap map emerges across three dimensions

The table below summarizes how the major systems cover the four requirements. No row has four checkmarks.

| System | MILP/MIP | Chemoenzymatic | Cost modeling | Confidence sensitivity |
|--------|:--------:|:--------------:|:------------:|:---------------------:|
| **SPARROW** (2024) | ✅ | ❌ | ✅ Real prices | ✅ λ-weight variation |
| **minChemBio** (2025) | ✅ | ✅ | ❌ Transition proxy | ❌ |
| **Gao et al.** (2020) | ✅ | ❌ | ❌ Inventory count | ✅ Pareto front |
| **novoStoic 2.0** (2025) | ✅ | ❌ Enzymatic only | ❌ | ❌ |
| **Retro-fallback** (2024) | ❌ Greedy | ❌ | ❌ | ✅ Stochastic SSP |
| **ASKCOS+enzymatic** (2022) | ❌ MCTS | ✅ | ✅ Partial | ❌ |
| **ChemEnzyRetroPlanner** (2025) | ❌ Tree search | ✅ | ❌ | ❌ |

The nearest path to a complete system would likely involve extending **SPARROW's** MILP framework (which already handles real cost data and confidence-weighted optimization) with enzymatic reaction templates — for example, incorporating the ~57,500 MetaNetX reactions used by minChemBio or the enzymatic templates from Levin et al. Alternatively, **minChemBio** could be extended with a cost-based objective function using ChemSpace or eMolecules pricing data, plus parametric variation of enzyme feasibility thresholds. Either route is technically feasible with existing components.

## Why this gap persists and what it would take to close it

The gap reflects disciplinary boundaries more than technical impossibility. The MILP retrosynthesis community (Coley, Jensen, and collaborators at MIT) works primarily in organic medicinal chemistry. The chemoenzymatic MILP community (Maranas group at Penn State) works primarily in metabolic engineering and biosynthesis. Neither group has fully bridged into the other's reaction space while simultaneously incorporating economic optimization and uncertainty quantification.

The process systems engineering (PSE) community — Grossmann, Pistikopoulos, Maravelias, and others — has **decades of experience** with stochastic MILP/MINLP for process design under uncertainty and pharmaceutical pipeline management under clinical trial uncertainty (Colvin & Maravelias, 2008–2011). The conceptual parallel is direct: binary reaction success/failure outcomes affecting investment decisions map cleanly onto binary reaction feasibility outcomes affecting route selection. Yet this PSE toolkit has **not been applied to retrosynthesis route selection**, representing perhaps the most promising methodological transfer opportunity.

Building the full four-part system would require: (1) a unified reaction database spanning chemical and enzymatic transformations with standardized atom mapping (minChemBio's USPTO+MetaNetX combination is a starting point); (2) a cost model incorporating reagent/starting material prices from commercial databases plus enzyme production or procurement cost estimates; (3) a MILP formulation with reaction selection as binary variables and a cost-based objective; and (4) either parametric sensitivity analysis (varying enzyme confidence thresholds and re-solving) or a stochastic programming formulation with scenario-based enzyme feasibility. Every individual component exists in published form — the integration does not.

## Conclusion

The exact four-part combination — MILP retrosynthesis with chemoenzymatic reactions, real cost modeling, and enzyme confidence sensitivity analysis — **does not exist** in the published literature as of February 2026. SPARROW achieves three of four (missing enzymatic), minChemBio achieves two (missing cost and sensitivity), and the Gao et al. 2020 Pareto analysis demonstrates the methodology for confidence sensitivity in a MILP retrosynthesis context but lacks enzymatic scope and cost data. The gap is not caused by missing algorithmic capability but by the disciplinary separation between organic retrosynthesis optimization, biosynthetic pathway design, and process systems engineering under uncertainty. A system combining SPARROW's cost-aware MILP framework with minChemBio's chemoenzymatic reaction space and the stochastic feasibility modeling of Retro-fallback would occupy a genuinely novel and practically valuable niche.
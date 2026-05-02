# Single-product dominance hypothesis test

We test if the solver generates solutions where one sellable product dominates the total return. We partition the 100,000-reaction parsed network (reactions.parquet) into **30** independent disjoint random subsets (~3,333 reactions each, shuffle seed 42) and run the MILP solver on each (budget=$10,000, --max-reactions 10). In each solution, we check the binary outcome of H₀ where no product dominates and H_a where only one product dominates, where *dominance* = top-product revenue / total revenue ≥ 0.50. We tested at a significance threshold of α = 0.01 via a one-sided exact binomial test against H₀: p ≤ 0.50.

## Result

- **30 of 30** trials produced a single-product-dominated solution
- median dominance ratio: 1.000
- mean dominance ratio: 1.000
- one-sided binomial p-value: **9.31e-10**
- α = 0.01 → **reject H₀**

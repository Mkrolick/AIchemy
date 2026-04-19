"""MILP solver package for AIchemy.

Formulates a Mixed-Integer Linear Program over the unified hypergraph
produced by the preprocessing pipeline, maximizing profit margin across
product selection and route selection jointly. Consumes the parquet
outputs of `data/processed/` (reactions + molecules).
"""

from aichemy.solver.config import SolverConfig
from aichemy.solver.model import Solution, build_and_solve

__all__ = ["Solution", "SolverConfig", "build_and_solve"]

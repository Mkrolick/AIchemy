"""Benchmarks + evaluation for AIchemy solver output.

Provides sanity checks and summary reports: does the MILP pick plausible
products, does profit fall in a reasonable range, are the most-activated
reactions well-known pathways?
"""

from aichemy.eval.benchmarks import (
    BenchmarkReport,
    known_profitable_molecules,
    summarize_solution,
)

__all__ = [
    "BenchmarkReport",
    "known_profitable_molecules",
    "summarize_solution",
]

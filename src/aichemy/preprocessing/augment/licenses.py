"""Merge license classifications onto reactions (Task 14).

Resolution rule (per `(rxn_id, patent_number)` pair):
- If `cpc_ambiguous` AND a matching LLM row exists → use LLM verdict.
- Else → use the CPC verdict.

Then OR-aggregate per `rxn_id` (a reaction with multiple patents — not
currently produced by upstream stages, but supported by this schema — gets
the OR across patents). Finally left-join onto the full reactions DataFrame
so MetaNetX rows (no patent association) end up with all flags False via
`fill_null(False)`.
"""

from __future__ import annotations

import polars as pl


def augment_licenses(
    reactions: pl.DataFrame,
    cpc: pl.DataFrame,
    llm: pl.DataFrame,
) -> pl.DataFrame:
    """Add patent_active, process_covered, composition_covered columns to reactions."""
    llm_renamed = llm.select(
        "patent_number",
        pl.col("process_covered").alias("process_covered_llm"),
        pl.col("composition_covered").alias("composition_covered_llm"),
    )

    resolved = (
        cpc.join(llm_renamed, on="patent_number", how="left")
        .with_columns(
            pl.when(pl.col("cpc_ambiguous") & pl.col("process_covered_llm").is_not_null())
            .then(pl.col("process_covered_llm"))
            .otherwise(pl.col("process_covered_cpc"))
            .alias("process_covered"),
            pl.when(pl.col("cpc_ambiguous") & pl.col("composition_covered_llm").is_not_null())
            .then(pl.col("composition_covered_llm"))
            .otherwise(pl.col("composition_covered_cpc"))
            .alias("composition_covered"),
        )
        .select("rxn_id", "patent_active", "process_covered", "composition_covered")
    )

    aggregated = resolved.group_by("rxn_id").agg(
        pl.col("patent_active").any().alias("patent_active"),
        pl.col("process_covered").any().alias("process_covered"),
        pl.col("composition_covered").any().alias("composition_covered"),
    )

    return reactions.join(aggregated, on="rxn_id", how="left").with_columns(
        pl.col("patent_active").fill_null(False),
        pl.col("process_covered").fill_null(False),
        pl.col("composition_covered").fill_null(False),
    )

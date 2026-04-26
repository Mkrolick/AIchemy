"""LLM patent classifier using the Anthropic SDK with structured tool-use.

The model is asked to judge two booleans (process_covered, composition_covered)
plus a self-reported confidence and one-sentence rationale. We use Claude's
tool-use schema to enforce structure rather than free-form JSON parsing.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from aichemy.preprocessing.patents.cache import LLMCacheEntry, append_cache, load_cache

log = logging.getLogger(__name__)


CLASSIFICATION_TOOL = {
    "name": "report_classification",
    "description": (
        "Report whether the given patent's claims cover the synthesis route "
        "(process) and/or any compound that participates in the reaction "
        "(composition-of-matter)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "process_covered": {
                "type": "boolean",
                "description": (
                    "True iff the patent's INDEPENDENT claims cover this specific "
                    "synthesis route (using these reactants, these conditions, this "
                    "transformation). Mere disclosure in examples or background does NOT count."
                ),
            },
            "composition_covered": {
                "type": "boolean",
                "description": (
                    "True iff the patent's INDEPENDENT claims cover any participant "
                    "compound (reactant, intermediate, or product) by composition-of-matter."
                ),
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Self-reported confidence in this classification.",
            },
            "rationale": {
                "type": "string",
                "description": (
                    "One sentence citing the specific claim/passage that supports the answer."
                ),
            },
        },
        "required": ["process_covered", "composition_covered", "confidence", "rationale"],
    },
}


SYSTEM_PROMPT = (
    "You are a patent-claims analyst. Given a USPTO patent's title, abstract, and "
    "independent claims, plus example reaction SMILES extracted from the patent, decide "
    "whether the patent's CLAIMS (not its background or examples) cover the reaction's "
    "synthesis route (process) and/or any participant compound by composition-of-matter. "
    "Be strict: only report True when the claims clearly cover the item. When in doubt, "
    "report False with a low confidence."
)


@dataclass
class LLMClassificationResult:
    process_covered: bool
    composition_covered: bool
    confidence: float
    rationale: str


def classify_patent_llm(
    *,
    client: Any,
    patent_number: str,
    title: str | None,
    abstract: str | None,
    claims_text: str | None,
    reaction_smiles_examples: list[str],
    model: str,
) -> LLMClassificationResult | None:
    """One LLM call, one classification. Returns None on unexpected stop_reason."""
    examples = "\n".join(reaction_smiles_examples[:5]) or "(none)"
    user = (
        f"Patent number: {patent_number}\n\n"
        f"Title: {title or '(none)'}\n\n"
        f"Abstract:\n{abstract or '(none)'}\n\n"
        f"Independent claims:\n{(claims_text or '(none)')[:8000]}\n\n"
        f"Reaction SMILES extracted from this patent:\n{examples}\n\n"
        "Use the report_classification tool."
    )
    msg = client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=[CLASSIFICATION_TOOL],
        tool_choice={"type": "tool", "name": "report_classification"},
        messages=[{"role": "user", "content": user}],
    )
    if msg.stop_reason != "tool_use":
        log.warning("Unexpected stop_reason=%s for patent=%s", msg.stop_reason, patent_number)
        return None
    for block in msg.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "report_classification":
            data = block.input
            return LLMClassificationResult(
                process_covered=bool(data["process_covered"]),
                composition_covered=bool(data["composition_covered"]),
                confidence=float(data["confidence"]),
                rationale=str(data["rationale"]),
            )
    return None


LLM_CLASSIFICATION_SCHEMA = {
    "patent_number": pl.Utf8,
    "process_covered": pl.Boolean,
    "composition_covered": pl.Boolean,
    "confidence": pl.Float64,
    "rationale": pl.Utf8,
    "model": pl.Utf8,
    "cache_hit": pl.Boolean,
}


def classify_ambiguous_patents(
    *,
    cpc: pl.DataFrame,
    patents: pl.DataFrame,
    reactions: pl.DataFrame,
    cache_path: Path,
    out_path: Path,
    client: Any,
    model: str,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
) -> pl.DataFrame:
    """Classify each unique patent flagged ambiguous + active.

    Cache hits don't call the LLM. Misses call once per patent (no retries
    on the LLM logic itself; transport-level retries on connection errors).
    Failed calls fall back to (False, False, 0.0) and are NOT cached.
    """
    target_patents = (
        cpc.filter(pl.col("cpc_ambiguous") & pl.col("patent_active"))
        .select("patent_number")
        .unique()["patent_number"]
        .to_list()
    )

    cache = load_cache(cache_path)
    rxn_smiles_by_patent = _smiles_index(cpc, reactions)
    patent_meta = {r["patent_number"]: r for r in patents.iter_rows(named=True)}

    rows: list[dict[str, Any]] = []
    for pn in target_patents:
        if pn in cache:
            entry = cache[pn]
            rows.append(_to_row(entry, cache_hit=True))
            continue

        meta = patent_meta.get(pn, {})
        result = _call_with_retry(
            client=client,
            model=model,
            patent_number=pn,
            abstract=meta.get("abstract"),
            claims_text=meta.get("claims_text"),
            smiles_examples=rxn_smiles_by_patent.get(pn, []),
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
        )
        if result is None:
            rows.append(
                {
                    "patent_number": pn,
                    "process_covered": False,
                    "composition_covered": False,
                    "confidence": 0.0,
                    "rationale": "LLM error — defaulted to no-license",
                    "model": model,
                    "cache_hit": False,
                }
            )
            continue
        entry = LLMCacheEntry(
            patent_number=pn,
            process_covered=result.process_covered,
            composition_covered=result.composition_covered,
            confidence=result.confidence,
            rationale=result.rationale,
            model=model,
            ts=datetime.now(tz=UTC).isoformat(),
        )
        append_cache(cache_path, entry)
        rows.append(_to_row(entry, cache_hit=False))

    df = pl.DataFrame(rows, schema=LLM_CLASSIFICATION_SCHEMA)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path)
    return df


def _smiles_index(cpc: pl.DataFrame, reactions: pl.DataFrame) -> dict[str, list[str]]:
    if "reaction_smiles" not in reactions.columns:
        return {}
    joined = cpc.select("rxn_id", "patent_number").join(
        reactions.select("rxn_id", "reaction_smiles"), on="rxn_id", how="inner"
    )
    out: dict[str, list[str]] = {}
    for r in joined.iter_rows(named=True):
        out.setdefault(r["patent_number"], []).append(r["reaction_smiles"])
    return out


def _call_with_retry(
    *,
    client: Any,
    model: str,
    patent_number: str,
    abstract: str | None,
    claims_text: str | None,
    smiles_examples: list[str],
    max_retries: int,
    backoff_seconds: float,
) -> LLMClassificationResult | None:
    for attempt in range(max_retries):
        try:
            return classify_patent_llm(
                client=client,
                patent_number=patent_number,
                title=None,
                abstract=abstract,
                claims_text=claims_text,
                reaction_smiles_examples=smiles_examples,
                model=model,
            )
        except Exception as exc:
            log.warning(
                "LLM call failed (attempt %d/%d) for patent=%s: %s",
                attempt + 1,
                max_retries,
                patent_number,
                exc,
            )
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2**attempt))
    return None


def _to_row(entry: LLMCacheEntry, *, cache_hit: bool) -> dict[str, Any]:
    return {
        "patent_number": entry.patent_number,
        "process_covered": entry.process_covered,
        "composition_covered": entry.composition_covered,
        "confidence": entry.confidence,
        "rationale": entry.rationale,
        "model": entry.model,
        "cache_hit": cache_hit,
    }

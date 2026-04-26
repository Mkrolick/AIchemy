"""LLM patent classifier using the Anthropic SDK with structured tool-use.

The model is asked to judge two booleans (process_covered, composition_covered)
plus a self-reported confidence and one-sentence rationale. We use Claude's
tool-use schema to enforce structure rather than free-form JSON parsing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

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
                "description": "One sentence citing the specific claim/passage that supports the answer.",
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
        log.warning(
            "Unexpected stop_reason=%s for patent=%s", msg.stop_reason, patent_number
        )
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

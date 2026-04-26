from unittest.mock import MagicMock

from aichemy.preprocessing.patents.llm_classify import (
    LLMClassificationResult,
    classify_patent_llm,
)


def _stub_anthropic_response(*, process: bool, composition: bool, confidence: float, rationale: str):
    """Build a mock that mimics anthropic.Anthropic().messages.create() returning tool-use."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = "report_classification"
    block.input = {
        "process_covered": process,
        "composition_covered": composition,
        "confidence": confidence,
        "rationale": rationale,
    }
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.content = [block]
    return msg


def test_classify_patent_llm_parses_tool_use():
    client = MagicMock()
    client.messages.create.return_value = _stub_anthropic_response(
        process=True, composition=False, confidence=0.86, rationale="claim 1 method",
    )
    out = classify_patent_llm(
        client=client,
        patent_number="7456123",
        title="A method",
        abstract="Method for synthesis…",
        claims_text="1. A process for…",
        reaction_smiles_examples=["A>>B"],
        model="claude-haiku-4-5",
    )
    assert isinstance(out, LLMClassificationResult)
    assert out.process_covered is True
    assert out.composition_covered is False
    assert out.confidence == 0.86
    assert out.rationale.startswith("claim")


def test_classify_patent_llm_returns_none_on_unexpected_stop_reason():
    client = MagicMock()
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = []
    client.messages.create.return_value = msg
    out = classify_patent_llm(
        client=client,
        patent_number="X",
        title="t", abstract="a", claims_text="c", reaction_smiles_examples=[],
        model="claude-haiku-4-5",
    )
    assert out is None

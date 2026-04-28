from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl

from aichemy.preprocessing.patents.cache import LLMCacheEntry, append_cache
from aichemy.preprocessing.patents.llm_classify import (
    LLM_CLASSIFICATION_SCHEMA,
    LLMClassificationResult,
    classify_ambiguous_patents,
    classify_patent_llm,
)


def _stub_anthropic_response(
    *, process: bool, composition: bool, confidence: float, rationale: str
):
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
        process=True,
        composition=False,
        confidence=0.86,
        rationale="claim 1 method",
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
        title="t",
        abstract="a",
        claims_text="c",
        reaction_smiles_examples=[],
        model="claude-haiku-4-5",
    )
    assert out is None


def test_classify_ambiguous_patents_uses_cache_when_present(tmp_path: Path):
    cache_path = tmp_path / "cache.jsonl"
    append_cache(
        cache_path,
        LLMCacheEntry(
            patent_number="A",
            process_covered=True,
            composition_covered=False,
            confidence=0.9,
            rationale="cached",
            model="claude-haiku-4-5",
            ts=datetime.now(tz=UTC).isoformat(),
        ),
    )
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:A:0"],
            "patent_number": ["A"],
            "patent_active": [True],
            "cpc_ambiguous": [True],
        }
    )
    patents = pl.DataFrame(
        {
            "patent_number": ["A"],
            "abstract": ["x"],
            "claims_text": ["1. claim"],
            "cpc_codes": [["A61K"]],
        }
    )
    reactions = pl.DataFrame({"rxn_id": ["USPTO:A:0"], "reaction_smiles": ["A>>B"]})
    client = MagicMock()
    out_path = tmp_path / "llm.parquet"
    out_df = classify_ambiguous_patents(
        cpc=cpc,
        patents=patents,
        reactions=reactions,
        cache_path=cache_path,
        out_path=out_path,
        client=client,
        model="claude-haiku-4-5",
        max_retries=1,
    )
    assert client.messages.create.call_count == 0  # cache hit
    assert out_df.height == 1
    assert out_df["cache_hit"][0] is True
    assert out_df["process_covered"][0] is True
    for col, dtype in LLM_CLASSIFICATION_SCHEMA.items():
        assert col in out_df.columns
        assert out_df.schema[col] == dtype


def test_classify_ambiguous_patents_calls_llm_on_cache_miss(tmp_path: Path):
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:B:0"],
            "patent_number": ["B"],
            "patent_active": [True],
            "cpc_ambiguous": [True],
        }
    )
    patents = pl.DataFrame(
        {
            "patent_number": ["B"],
            "abstract": ["xyz"],
            "claims_text": ["1. claim"],
            "cpc_codes": [["A61K"]],
        }
    )
    reactions = pl.DataFrame({"rxn_id": ["USPTO:B:0"], "reaction_smiles": ["A>>B"]})
    client = MagicMock()
    client.messages.create.return_value = _stub_anthropic_response(
        process=False,
        composition=True,
        confidence=0.7,
        rationale="composition only",
    )
    cache_path = tmp_path / "cache.jsonl"
    out_path = tmp_path / "llm.parquet"
    out_df = classify_ambiguous_patents(
        cpc=cpc,
        patents=patents,
        reactions=reactions,
        cache_path=cache_path,
        out_path=out_path,
        client=client,
        model="claude-haiku-4-5",
        max_retries=1,
    )
    assert client.messages.create.call_count == 1
    assert out_df["cache_hit"][0] is False
    assert out_df["composition_covered"][0] is True
    # Cache file now has one entry
    assert cache_path.exists()
    assert "B" in cache_path.read_text()


def test_classify_ambiguous_patents_skips_inactive(tmp_path: Path):
    cpc = pl.DataFrame(
        {
            "rxn_id": ["USPTO:C:0"],
            "patent_number": ["C"],
            "patent_active": [False],
            "cpc_ambiguous": [True],
        }
    )
    patents = pl.DataFrame(
        {"patent_number": ["C"], "abstract": [None], "claims_text": [None], "cpc_codes": [[]]}
    )
    reactions = pl.DataFrame({"rxn_id": ["USPTO:C:0"], "reaction_smiles": ["A>>B"]})
    client = MagicMock()
    out_path = tmp_path / "llm.parquet"
    out_df = classify_ambiguous_patents(
        cpc=cpc,
        patents=patents,
        reactions=reactions,
        cache_path=tmp_path / "cache.jsonl",
        out_path=out_path,
        client=client,
        model="claude-haiku-4-5",
        max_retries=1,
    )
    # Inactive patents are not LLM-classified
    assert out_df.height == 0
    assert client.messages.create.call_count == 0

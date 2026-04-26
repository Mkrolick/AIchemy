from pathlib import Path

import yaml

from aichemy.config import LicensesConfig, load_config


def test_licenses_config_defaults():
    cfg = LicensesConfig()
    assert cfg.patentsview_endpoint == "https://api.uspto.gov/api/v1/patent/applications/search"
    assert cfg.llm_model == "claude-haiku-4-5"
    assert cfg.cpc_rules_path == Path("configs/cpc_rules.yaml")
    assert cfg.cache_path == Path("data/interim/licenses/llm_cache.jsonl")
    assert cfg.fetch_batch_size == 25
    assert cfg.fetch_max_retries == 3
    assert cfg.llm_max_retries == 3


def test_preprocessing_config_includes_licenses(tmp_path: Path):
    base = tmp_path / "base.yaml"
    base.write_text(yaml.safe_dump({}))
    cfg = load_config(base, [])
    assert cfg.licenses.llm_model == "claude-haiku-4-5"

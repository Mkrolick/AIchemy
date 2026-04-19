import textwrap
from pathlib import Path

import pytest
from aichemy.config import (
    DedupConfig,
    FilterConfig,
    PathsConfig,
    PreprocessingConfig,
    PricesConfig,
    SourcesConfig,
    YieldConfig,
    YieldImputationStrategy,
    load_config,
)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(body))
    return path


def test_defaults() -> None:
    cfg = PreprocessingConfig()
    assert cfg.dedup.tanimoto_threshold == 1.0
    assert cfg.dedup.reaction_tanimoto_threshold == 0.95
    assert cfg.dedup.fingerprint_radius == 2
    assert cfg.dedup.fingerprint_bits == 2048
    assert cfg.filter.min_carbon_count == 2
    assert cfg.yields.strategy == YieldImputationStrategy.GLOBAL_MEAN
    assert cfg.yields.fixed_value == 0.85
    assert cfg.yields.enzymatic_prior_range == (0.85, 0.95)
    assert cfg.sources.metanetx_version == "4.4"
    assert cfg.sources.uspto_slice == "grants_1976_2016"
    assert cfg.prices.backend == "stub"
    assert cfg.paths.data_dir == Path("data")


def test_subconfigs_are_own_models() -> None:
    assert isinstance(PreprocessingConfig().dedup, DedupConfig)
    assert isinstance(PreprocessingConfig().filter, FilterConfig)
    assert isinstance(PreprocessingConfig().yields, YieldConfig)
    assert isinstance(PreprocessingConfig().sources, SourcesConfig)
    assert isinstance(PreprocessingConfig().prices, PricesConfig)
    assert isinstance(PreprocessingConfig().paths, PathsConfig)


def test_loads_base_yaml(tmp_path: Path) -> None:
    base = _write(
        tmp_path,
        "default.yaml",
        """
        dedup:
          tanimoto_threshold: 0.9
        filter:
          min_carbon_count: 3
        """,
    )
    cfg = load_config(base)
    assert cfg.dedup.tanimoto_threshold == 0.9
    assert cfg.filter.min_carbon_count == 3
    assert cfg.dedup.reaction_tanimoto_threshold == 0.95  # default preserved


def test_override_replaces_scalar(tmp_path: Path) -> None:
    base = _write(tmp_path, "b.yaml", "dedup:\n  tanimoto_threshold: 0.9\n")
    override = _write(tmp_path, "o.yaml", "dedup:\n  tanimoto_threshold: 0.5\n")
    cfg = load_config(base, [override])
    assert cfg.dedup.tanimoto_threshold == 0.5


def test_override_deep_merges_dict(tmp_path: Path) -> None:
    base = _write(
        tmp_path,
        "b.yaml",
        """
        dedup:
          tanimoto_threshold: 0.9
          fingerprint_radius: 2
        """,
    )
    override = _write(tmp_path, "o.yaml", "dedup:\n  fingerprint_radius: 3\n")
    cfg = load_config(base, [override])
    assert cfg.dedup.tanimoto_threshold == 0.9  # from base, untouched
    assert cfg.dedup.fingerprint_radius == 3  # from override


def test_override_replaces_list(tmp_path: Path) -> None:
    """Lists/tuples must be REPLACED, not concatenated (per spec)."""
    base = _write(
        tmp_path,
        "b.yaml",
        "yields:\n  enzymatic_prior_range: [0.85, 0.95]\n",
    )
    override = _write(
        tmp_path,
        "o.yaml",
        "yields:\n  enzymatic_prior_range: [0.90, 0.99]\n",
    )
    cfg = load_config(base, [override])
    assert cfg.yields.enzymatic_prior_range == (0.90, 0.99)


def test_multiple_overrides_apply_in_order(tmp_path: Path) -> None:
    base = _write(tmp_path, "b.yaml", "dedup:\n  tanimoto_threshold: 0.9\n")
    o1 = _write(tmp_path, "o1.yaml", "dedup:\n  tanimoto_threshold: 0.5\n")
    o2 = _write(tmp_path, "o2.yaml", "dedup:\n  tanimoto_threshold: 0.3\n")
    cfg = load_config(base, [o1, o2])
    assert cfg.dedup.tanimoto_threshold == 0.3  # last override wins


def test_invalid_key_raises(tmp_path: Path) -> None:
    from pydantic import ValidationError

    base = _write(tmp_path, "b.yaml", "dedup:\n  tanimoto_threshold: 0.9\n")
    override = _write(tmp_path, "o.yaml", "dedup:\n  nonexistent_key: 42\n")
    with pytest.raises(ValidationError):
        load_config(base, [override])


def test_default_yaml_parses() -> None:
    """configs/default.yaml should load and produce exactly the Pydantic defaults."""
    repo_root = Path(__file__).resolve().parents[2]
    default_path = repo_root / "configs" / "default.yaml"
    cfg = load_config(default_path)
    expected = PreprocessingConfig()
    assert cfg == expected


def test_strict_dedup_profile_applies() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    default_path = repo_root / "configs" / "default.yaml"
    profile_path = repo_root / "configs" / "profiles" / "strict_dedup.yaml"
    cfg = load_config(default_path, [profile_path])
    assert cfg.dedup.reaction_tanimoto_threshold == 1.0  # stricter than 0.95 default


def test_mean_yields_profile_applies() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    default_path = repo_root / "configs" / "default.yaml"
    profile_path = repo_root / "configs" / "profiles" / "mean_yields.yaml"
    cfg = load_config(default_path, [profile_path])
    assert cfg.yields.strategy == YieldImputationStrategy.PER_EC_CLASS

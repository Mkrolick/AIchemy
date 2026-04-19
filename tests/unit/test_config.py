from pathlib import Path

from aichemy.config import (
    DedupConfig,
    FilterConfig,
    PathsConfig,
    PreprocessingConfig,
    PricesConfig,
    SourcesConfig,
    YieldConfig,
    YieldImputationStrategy,
)


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

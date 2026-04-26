from pathlib import Path

from aichemy.config import PreprocessingConfig
from aichemy.preprocessing.io import licenses_path, patents_path


def test_patents_path():
    cfg = PreprocessingConfig()
    assert patents_path(cfg, "patent_metadata.parquet") == Path(
        "data/interim/patents/patent_metadata.parquet"
    )


def test_licenses_path():
    cfg = PreprocessingConfig()
    assert licenses_path(cfg, "cpc_classifications.parquet") == Path(
        "data/interim/licenses/cpc_classifications.parquet"
    )

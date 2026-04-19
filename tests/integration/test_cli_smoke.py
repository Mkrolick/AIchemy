from pathlib import Path

import pytest
from typer.testing import CliRunner

from aichemy.cli import app

runner = CliRunner()


def test_help_lists_all_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in [
        "fetch-raw",
        "ingest",
        "normalize",
        "dedup",
        "balance",
        "augment",
        "export",
    ]:
        assert name in result.stdout


@pytest.mark.parametrize(
    "cmd",
    [
        ["fetch-raw", "--help"],
        ["ingest", "metanetx", "--help"],
        ["ingest", "uspto", "--help"],
        ["normalize", "--help"],
        ["dedup", "molecules", "--help"],
        ["dedup", "reactions", "--help"],
        ["balance", "uspto", "--help"],
        ["balance", "validate", "--help"],
        ["augment", "yields", "--help"],
        ["augment", "prices", "--help"],
        ["augment", "directionality", "--help"],
        ["export", "--help"],
    ],
)
def test_subcommand_help_works(cmd: list[str]) -> None:
    result = runner.invoke(app, cmd)
    assert result.exit_code == 0


def test_fetch_raw_stub_creates_raw_directories(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.yaml"
    config_path.write_text(f"paths:\n  data_dir: {tmp_path}\n")
    result = runner.invoke(app, ["fetch-raw", "--config", str(config_path)])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "raw" / "metanetx").is_dir()
    assert (tmp_path / "raw" / "uspto").is_dir()


def test_ingest_metanetx_stub_creates_empty_parquets(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.yaml"
    config_path.write_text(f"paths:\n  data_dir: {tmp_path}\n")
    result = runner.invoke(app, ["ingest", "metanetx", "--config", str(config_path)])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "interim" / "metanetx" / "reactions_raw.parquet").exists()
    assert (tmp_path / "interim" / "metanetx" / "molecules_raw.parquet").exists()


def test_export_stub_creates_processed_parquets(tmp_path: Path) -> None:
    config_path = tmp_path / "cfg.yaml"
    config_path.write_text(f"paths:\n  data_dir: {tmp_path}\n")
    result = runner.invoke(app, ["export", "--config", str(config_path)])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "processed" / "reactions.parquet").exists()
    assert (tmp_path / "processed" / "molecules.parquet").exists()

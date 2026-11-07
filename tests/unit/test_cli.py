"""Tests for the CLI entry point and foundation commands."""

import json
from pathlib import Path

from typer.testing import CliRunner

from cii import __version__
from cii.cli.commands import app

runner = CliRunner()


class TestVersion:
    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.stdout.strip() == f"cii {__version__}"


class TestInit:
    def test_creates_structure(self, project_root: Path) -> None:
        result = runner.invoke(app, ["init", "--root", str(project_root)])
        assert result.exit_code == 0
        assert (project_root / ".cii" / "config.toml").is_file()
        assert (project_root / ".cii" / "cache").is_dir()
        assert (project_root / ".cii" / "logs").is_dir()
        assert "CII initialised" in result.stdout

    def test_creates_database_and_registers_project(self, project_root: Path) -> None:
        result = runner.invoke(app, ["init", "--root", str(project_root), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["database_healthy"] is True
        assert payload["project_id"]
        assert (project_root / ".cii" / "cii.db").is_file()

    def test_json_output(self, project_root: Path) -> None:
        result = runner.invoke(app, ["init", "--root", str(project_root), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["config_created"] is True
        assert payload["project_root"] == str(project_root.resolve())

    def test_idempotent_preserves_existing_config(self, project_root: Path) -> None:
        assert runner.invoke(app, ["init", "--root", str(project_root)]).exit_code == 0
        config_path = project_root / ".cii" / "config.toml"
        config_path.write_text(config_path.read_text().replace('name = ""', 'name = "mine"'))

        result = runner.invoke(app, ["init", "--root", str(project_root), "--json"])
        assert result.exit_code == 0
        assert json.loads(result.stdout)["config_created"] is False
        assert 'name = "mine"' in config_path.read_text()

    def test_missing_root_fails_cleanly(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["init", "--root", str(tmp_path / "missing")])
        assert result.exit_code == 1
        assert "error:" in result.output


class TestConfig:
    def test_shows_defaults(self, project_root: Path) -> None:
        result = runner.invoke(app, ["config", "--root", str(project_root)])
        assert result.exit_code == 0
        assert "[scan]" in result.stdout
        assert "hash_algorithm = sha256" in result.stdout

    def test_json_output_matches_defaults(self, project_root: Path) -> None:
        result = runner.invoke(app, ["config", "--root", str(project_root), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["scan"]["hash_algorithm"] == "sha256"
        assert payload["logging"]["level"] == "INFO"

    def test_reflects_project_overrides(self, project_root: Path) -> None:
        assert runner.invoke(app, ["init", "--root", str(project_root)]).exit_code == 0
        config_path = project_root / ".cii" / "config.toml"
        config_path.write_text(config_path.read_text().replace('level = "INFO"', 'level = "DEBUG"'))
        result = runner.invoke(app, ["config", "--root", str(project_root), "--json"])
        assert json.loads(result.stdout)["logging"]["level"] == "DEBUG"

    def test_broken_config_fails_cleanly(self, project_root: Path) -> None:
        (project_root / ".cii").mkdir()
        (project_root / ".cii" / "config.toml").write_text("[[[broken")
        result = runner.invoke(app, ["config", "--root", str(project_root)])
        assert result.exit_code == 1
        assert "error:" in result.output


class TestStatus:
    def test_status_without_init_fails(self, project_root: Path) -> None:
        result = runner.invoke(app, ["status", "--root", str(project_root)])
        assert result.exit_code == 1
        combined = result.output + (getattr(result, "stderr", "") or "")
        assert "not initialised" in combined

    def test_status_after_init(self, project_root: Path) -> None:
        assert runner.invoke(app, ["init", "--root", str(project_root)]).exit_code == 0
        result = runner.invoke(app, ["status", "--root", str(project_root), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["database_healthy"] is True
        assert payload["indexed_files"] == 0
        assert payload["indexed_symbols"] == 0
        assert payload["last_scan"] is None

    def test_status_human_output(self, project_root: Path) -> None:
        assert runner.invoke(app, ["init", "--root", str(project_root)]).exit_code == 0
        result = runner.invoke(app, ["status", "--root", str(project_root)])
        assert result.exit_code == 0
        assert "Index:        v1.0" in result.stdout
        assert "Files:        0 indexed" in result.stdout

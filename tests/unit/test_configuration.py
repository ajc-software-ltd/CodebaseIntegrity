"""Tests for configuration loading, merging, and validation."""

import tomllib
from pathlib import Path

import pytest

from cii.core.configuration import (
    DEFAULT_EXCLUDED_DIRECTORIES,
    CiiConfig,
    config_hash,
    load_config,
    parse_config,
    project_config_path,
    save_project_config,
)
from cii.core.exceptions import ConfigurationError


class TestDefaults:
    def test_defaults_match_spec(self) -> None:
        config = CiiConfig.defaults()
        assert config.scan.excluded_directories == DEFAULT_EXCLUDED_DIRECTORIES
        assert config.scan.max_file_size_bytes == 2_097_152
        assert config.scan.hash_algorithm == "sha256"
        assert config.languages.extensions[".cpp"] == "cpp"
        assert config.languages.extensions[".py"] == "python"
        assert config.output.markdown_index is True
        assert config.logging.level == "INFO"

    def test_defaults_are_fresh_objects(self) -> None:
        first = CiiConfig.defaults()
        first.scan.excluded_directories.append("mutated")
        assert "mutated" not in CiiConfig.defaults().scan.excluded_directories


class TestParseConfig:
    def test_overlay_merges_over_defaults(self) -> None:
        config = parse_config({"logging": {"level": "DEBUG"}})
        assert config.logging.level == "DEBUG"
        assert config.logging.console is True

    def test_extension_overlay_merges_per_key(self) -> None:
        config = parse_config({"languages": {"extensions": {".glsl": "cpp", ".CPP": "cpp"}}})
        assert config.languages.extensions[".glsl"] == "cpp"
        assert config.languages.extensions[".cpp"] == "cpp"
        assert config.languages.extensions[".py"] == "python"

    def test_unknown_key_rejected(self) -> None:
        with pytest.raises(ConfigurationError, match="invalid configuration"):
            parse_config({"scan": {"not_a_setting": 1}})

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ConfigurationError):
            parse_config({"scan": {"max_file_size_bytes": 0}})

    def test_unknown_language_rejected(self) -> None:
        with pytest.raises(ConfigurationError):
            parse_config({"languages": {"extensions": {".rs": "rust"}}})

    def test_extension_without_dot_rejected(self) -> None:
        with pytest.raises(ConfigurationError):
            parse_config({"languages": {"extensions": {"cpp": "cpp"}}})

    def test_invalid_log_level_rejected(self) -> None:
        with pytest.raises(ConfigurationError):
            parse_config({"logging": {"level": "VERBOSE"}})


class TestLoadConfig:
    def test_without_config_file_returns_defaults(self, project_root: Path) -> None:
        config = load_config(project_root)
        assert config == CiiConfig.defaults()

    def test_loads_project_overrides(self, project_root: Path) -> None:
        save_project_config(parse_config({"project": {"name": "demo"}}), project_root)
        config = load_config(project_root)
        assert config.project.name == "demo"

    def test_invalid_toml_raises(self, project_root: Path) -> None:
        config_path = project_config_path(project_root)
        config_path.parent.mkdir(parents=True)
        config_path.write_text("this is [not valid toml")
        with pytest.raises(ConfigurationError, match="cannot read configuration"):
            load_config(project_root)

    def test_invalid_schema_raises_with_source(self, project_root: Path) -> None:
        config_path = project_config_path(project_root)
        config_path.parent.mkdir(parents=True)
        config_path.write_text('[scan]\nmax_file_size_bytes = 0\n')
        with pytest.raises(ConfigurationError) as exc_info:
            load_config(project_root)
        assert "config.toml" in str(exc_info.value)


class TestSaveProjectConfig:
    def test_round_trip(self, project_root: Path) -> None:
        original = parse_config(
            {"project": {"name": "round-trip"}, "scan": {"max_file_size_bytes": 7}}
        )
        config_path = save_project_config(original, project_root)
        assert config_path == project_config_path(project_root)
        assert load_config(project_root) == original

    def test_written_file_is_valid_toml(self, project_root: Path) -> None:
        config_path = save_project_config(CiiConfig.defaults(), project_root)
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
        assert data["scan"]["hash_algorithm"] == "sha256"


class TestConfigHash:
    def test_deterministic(self) -> None:
        assert config_hash(CiiConfig.defaults()) == config_hash(CiiConfig.defaults())

    def test_changes_with_configuration(self) -> None:
        changed = parse_config({"logging": {"level": "DEBUG"}})
        assert config_hash(changed) != config_hash(CiiConfig.defaults())

"""Configuration management.

Defaults are defined by the Pydantic models below. ``config/default.toml`` in
the repository is a reference copy of those defaults (kept in sync by
``tests/unit/test_default_config_sync.py``). Project-specific overrides live
in ``<project-root>/.cii/config.toml`` and are deep-merged over the defaults.

The configuration schema covers the scanner, language mapping, output, and
logging. Later milestones extend it as their subsystems land; every extension
must add its defaults to the models *and* to ``config/default.toml``.
"""

import hashlib
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from cii.core.enums import Language
from cii.core.exceptions import ConfigurationError
from cii.utilities.paths import cii_data_dir
from cii.utilities.serialization import dump_toml

CONFIG_FILE_NAME = "config.toml"

DEFAULT_EXCLUDED_DIRECTORIES: list[str] = [
    ".git",
    ".cii",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".cache",
    "build",
    "dist",
    "out",
    "bin",
    "obj",
    "cmake-build-debug",
    "cmake-build-release",
    "generated",
    "third_party",
    "vendor",
]

DEFAULT_EXTENSIONS: dict[str, str] = {
    ".c": "c",
    ".h": "cpp",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".cs": "csharp",
    ".py": "python",
}


class ProjectSettings(BaseModel):
    """Project identity settings."""

    model_config = {"extra": "forbid"}

    # Empty string means "derive from the project directory name".
    name: str = ""


class ScanSettings(BaseModel):
    """Filesystem scanning and change detection settings."""

    model_config = {"extra": "forbid"}

    excluded_directories: list[str] = Field(
        default_factory=lambda: list(DEFAULT_EXCLUDED_DIRECTORIES)
    )
    included_directories: list[str] = Field(default_factory=list)
    max_file_size_bytes: int = Field(default=2_097_152, gt=0)
    follow_symlinks: bool = False
    detect_generated_files: bool = True
    hash_algorithm: Literal["sha256"] = "sha256"


class LanguageSettings(BaseModel):
    """File extension to language mapping."""

    model_config = {"extra": "forbid"}

    extensions: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_EXTENSIONS))

    @field_validator("extensions")
    @classmethod
    def _validate_extensions(cls, value: dict[str, str]) -> dict[str, str]:
        known_languages = {language.value for language in Language}
        normalised: dict[str, str] = {}
        for extension, language in value.items():
            if not extension.startswith("."):
                raise ValueError(f"extension must start with '.': {extension!r}")
            if language not in known_languages:
                raise ValueError(f"unknown language {language!r} for extension {extension!r}")
            normalised[extension.lower()] = language
        return normalised


class OutputSettings(BaseModel):
    """Generated index output settings."""

    model_config = {"extra": "forbid"}

    markdown_index: bool = True
    split_by_language: bool = False
    commit_index: bool = False


class LoggingSettings(BaseModel):
    """Logging settings."""

    model_config = {"extra": "forbid"}

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    console: bool = True
    file: bool = True


class CiiConfig(BaseModel):
    """Complete CII configuration."""

    model_config = {"extra": "forbid"}

    project: ProjectSettings = Field(default_factory=ProjectSettings)
    scan: ScanSettings = Field(default_factory=ScanSettings)
    languages: LanguageSettings = Field(default_factory=LanguageSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @classmethod
    def defaults(cls) -> "CiiConfig":
        """Return the built-in default configuration."""
        return cls()


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` into ``base`` (overlay wins)."""
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def project_config_path(project_root: Path) -> Path:
    """Return the path of the project configuration file."""
    return cii_data_dir(project_root) / CONFIG_FILE_NAME


def load_config(project_root: Path) -> CiiConfig:
    """Load the effective configuration for ``project_root``.

    Built-in defaults are overlaid with ``<project_root>/.cii/config.toml``
    when that file exists.
    """
    config_path = project_config_path(project_root)
    if not config_path.is_file():
        return CiiConfig.defaults()
    try:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(f"cannot read configuration {config_path}: {error}") from error
    return parse_config(data, source=str(config_path))


def parse_config(data: dict[str, Any], *, source: str = "<config>") -> CiiConfig:
    """Validate raw configuration data against the schema.

    Raises:
        ConfigurationError: the data does not match the configuration schema.
    """
    merged = _deep_merge(CiiConfig.defaults().model_dump(mode="python"), data)
    try:
        return CiiConfig.model_validate(merged)
    except ValidationError as error:
        raise ConfigurationError(f"invalid configuration in {source}: {error}") from error


def save_project_config(config: CiiConfig, project_root: Path) -> Path:
    """Write the configuration to ``<project_root>/.cii/config.toml``.

    The parent ``.cii`` directory is created when missing.
    """
    config_path = project_config_path(project_root)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(dump_toml(config.model_dump(mode="python")), encoding="utf-8")
    return config_path


def config_hash(config: CiiConfig) -> str:
    """Canonical fingerprint of an effective configuration (SHA-256 of its TOML)."""
    canonical = dump_toml(config.model_dump(mode="python")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

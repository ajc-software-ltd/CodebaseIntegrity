"""Keeps config/default.toml in sync with the code defaults.

The repository's config/default.toml is a user-facing reference copy of the
built-in defaults. Whenever a settings model changes, this test forces the
reference file to be updated in the same change.
"""

import tomllib
from pathlib import Path

from cii.core.configuration import CiiConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "default.toml"


def test_default_config_file_matches_code_defaults() -> None:
    assert DEFAULT_CONFIG_PATH.is_file(), "config/default.toml is missing"
    with DEFAULT_CONFIG_PATH.open("rb") as handle:
        file_data = tomllib.load(handle)
    code_defaults = CiiConfig.defaults().model_dump(mode="python")
    assert file_data == code_defaults, (
        "config/default.toml is out of sync with the code defaults in "
        "src/cii/core/configuration.py — update both together"
    )

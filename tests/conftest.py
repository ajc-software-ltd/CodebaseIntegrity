"""Shared pytest fixtures for the CII test suite."""

from pathlib import Path

import pytest


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """An empty project root directory."""
    root = tmp_path / "proj"
    root.mkdir()
    return root

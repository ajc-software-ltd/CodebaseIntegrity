"""Fixtures for database tests."""

from pathlib import Path

import pytest

from cii.database.database import Database


@pytest.fixture
def database(project_root: Path):
    """An open, freshly migrated database for the test project."""
    with Database.open(project_root) as db:
        yield db

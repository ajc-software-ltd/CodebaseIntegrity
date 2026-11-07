"""Tests for filesystem path handling and project-root containment."""

from pathlib import Path

import pytest

from cii.core.exceptions import PathSecurityError
from cii.utilities.paths import (
    cii_data_dir,
    find_project_root,
    is_within_root,
    require_within_root,
    resolve_project_root,
    to_relative_posix,
    validate_relative_path,
)


class TestResolveProjectRoot:
    def test_resolves_existing_directory(self, tmp_path: Path) -> None:
        assert resolve_project_root(tmp_path) == tmp_path.resolve()

    def test_missing_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises(Exception, match="does not exist"):
            resolve_project_root(tmp_path / "missing")

    def test_file_raises(self, tmp_path: Path) -> None:
        file_path = tmp_path / "file.txt"
        file_path.write_text("x")
        with pytest.raises(Exception, match="not a directory"):
            resolve_project_root(file_path)


class TestContainment:
    def test_path_inside_root(self, project_root: Path) -> None:
        assert is_within_root(project_root / "src" / "main.cpp", project_root)

    def test_path_outside_root(self, project_root: Path, tmp_path: Path) -> None:
        assert not is_within_root(tmp_path / "elsewhere", project_root)

    def test_traversal_rejected(self, project_root: Path) -> None:
        assert not is_within_root(project_root / "a" / ".." / "..", project_root)

    def test_symlink_escaping_root_rejected(self, project_root: Path, tmp_path: Path) -> None:
        outside = tmp_path / "outside.txt"
        outside.write_text("data")
        link = project_root / "link.txt"
        link.symlink_to(outside)
        assert not is_within_root(link, project_root)

    def test_require_within_root_raises(self, project_root: Path, tmp_path: Path) -> None:
        with pytest.raises(PathSecurityError, match="escapes the project root"):
            require_within_root(tmp_path / "elsewhere", project_root)

    def test_to_relative_posix(self, project_root: Path) -> None:
        assert to_relative_posix(project_root / "src" / "a.cpp", project_root) == "src/a.cpp"

    def test_cii_data_dir(self, project_root: Path) -> None:
        assert cii_data_dir(project_root) == project_root / ".cii"


class TestValidateRelativePath:
    @pytest.mark.parametrize("value", ["src/a.cpp", "a.py", "deep/nested/file.hpp", "with space.c"])
    def test_valid(self, value: str) -> None:
        assert validate_relative_path(value) == value

    @pytest.mark.parametrize(
        "value",
        ["", "/abs/path", "\\windows\\path", "C:\\windows\\path", "a/../b", "..", "a/.."],
    )
    def test_invalid(self, value: str) -> None:
        with pytest.raises(PathSecurityError):
            validate_relative_path(value)

    def test_backslashes_normalised(self) -> None:
        assert validate_relative_path("src\\a.cpp") == "src/a.cpp"


class TestFindProjectRoot:
    def test_finds_root_from_nested_directory(self, project_root: Path) -> None:
        (project_root / ".cii").mkdir()
        nested = project_root / "src" / "deep"
        nested.mkdir(parents=True)
        assert find_project_root(nested) == project_root.resolve()

    def test_returns_none_without_cii(self, tmp_path: Path) -> None:
        assert find_project_root(tmp_path) is None

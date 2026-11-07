"""Filesystem path handling with project-root containment guarantees.

Every path that enters CII from configuration, CLI arguments, or MCP tool
inputs must resolve inside the configured project root. These helpers are the
single place where that policy is enforced.
"""

import os
from pathlib import Path, PureWindowsPath

from cii.core.exceptions import PathSecurityError, ProjectRootError

CII_DIR_NAME = ".cii"


def cii_data_dir(project_root: Path) -> Path:
    """Return the CII data directory (``<project_root>/.cii``)."""
    return project_root / CII_DIR_NAME


def resolve_project_root(root: Path | str) -> Path:
    """Resolve and validate a project root directory.

    Raises:
        ProjectRootError: the path does not exist or is not a directory.
    """
    resolved = Path(root).expanduser().resolve()
    if not resolved.exists():
        raise ProjectRootError(f"project root does not exist: {root}")
    if not resolved.is_dir():
        raise ProjectRootError(f"project root is not a directory: {root}")
    return resolved


def is_within_root(path: Path | str, root: Path) -> bool:
    """Return True when ``path`` resolves inside ``root``.

    Symlinks are resolved first, so a link pointing outside the project root
    is *not* considered within it (PLAN.md §7.3, §19).
    """
    resolved = Path(path).expanduser().resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def require_within_root(path: Path | str, root: Path) -> Path:
    """Resolve ``path`` and require it to be inside ``root``.

    Returns the resolved path.

    Raises:
        PathSecurityError: the path escapes the project root.
    """
    resolved = Path(path).expanduser().resolve()
    if not is_within_root(resolved, root):
        raise PathSecurityError(f"path escapes the project root: {path}")
    return resolved


def to_relative_posix(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` using POSIX separators.

    Raises:
        PathSecurityError: the path is not inside ``root``.
    """
    resolved = require_within_root(path, root)
    return resolved.relative_to(root.resolve()).as_posix()


def validate_relative_path(value: str) -> str:
    """Validate a project-relative POSIX path string used in models/DB rows.

    Raises:
        PathSecurityError: the value is absolute or contains traversal segments.
    """
    if not value:
        raise PathSecurityError("path must not be empty")
    if os.path.isabs(value) or value.startswith("/") or value.startswith("\\"):
        raise PathSecurityError(f"path must be relative, got: {value}")
    if PureWindowsPath(value).is_absolute():
        # Reject Windows-style absolute paths too, so records stay portable.
        raise PathSecurityError(f"path must be relative, got: {value}")
    parts = value.replace("\\", "/").split("/")
    if any(part == ".." for part in parts):
        raise PathSecurityError(f"path must not contain traversal segments: {value}")
    return value.replace("\\", "/")


def find_project_root(start: Path | str) -> Path | None:
    """Walk upward from ``start`` looking for an existing CII data directory.

    Returns the containing project root, or None when no ``.cii`` directory is
    found up to the filesystem root.
    """
    current = Path(start).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / CII_DIR_NAME).is_dir():
            return candidate
    return None

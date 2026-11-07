"""Tests for content hashing."""

import hashlib
from pathlib import Path

import pytest

from cii.scanner.file_hash import hash_file


class TestHashFile:
    def test_known_content(self, tmp_path: Path) -> None:
        path = tmp_path / "a.txt"
        path.write_bytes(b"hello")
        assert hash_file(path) == hashlib.sha256(b"hello").hexdigest()

    def test_streams_large_file(self, tmp_path: Path) -> None:
        path = tmp_path / "big.bin"
        content = b"x" * 300_000  # several chunks
        path.write_bytes(content)
        assert hash_file(path) == hashlib.sha256(content).hexdigest()

    def test_unsupported_algorithm(self, tmp_path: Path) -> None:
        path = tmp_path / "a.txt"
        path.write_bytes(b"data")
        with pytest.raises(ValueError, match="unsupported hash algorithm"):
            hash_file(path, "md4")

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            hash_file(tmp_path / "missing.txt")

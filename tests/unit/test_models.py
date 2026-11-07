"""Tests for core domain models."""

import pytest
from pydantic import ValidationError

from cii.core.enums import IntegrityStatus, Language, ScanStatus, SymbolType, Visibility
from cii.core.models import FileRecord, IndexStatus, SymbolCounts, SymbolInfo


class TestSymbolCounts:
    def test_defaults_are_zero(self) -> None:
        counts = SymbolCounts()
        assert counts.total == 0

    def test_total_sums_all_counts(self) -> None:
        counts = SymbolCounts(namespaces=1, classes=2, functions=3, methods=4)
        assert counts.total == 10

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SymbolCounts(classes=-1)


class TestSymbolInfo:
    def test_minimal_symbol(self) -> None:
        symbol = SymbolInfo(
            name="initialize",
            fully_qualified_name="VulkanRenderer::initialize",
            symbol_type=SymbolType.METHOD,
            language=Language.CPP,
            file_path="src/VulkanRenderer.cpp",
        )
        assert symbol.visibility == Visibility.UNKNOWN
        assert symbol.parent is None

    def test_absolute_file_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SymbolInfo(
                name="main",
                fully_qualified_name="main",
                symbol_type=SymbolType.FUNCTION,
                language=Language.C,
                file_path="/etc/passwd",
            )

    def test_traversal_file_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SymbolInfo(
                name="main",
                fully_qualified_name="main",
                symbol_type=SymbolType.FUNCTION,
                language=Language.C,
                file_path="src/../../secret.c",
            )

    def test_zero_start_line_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SymbolInfo(
                name="main",
                fully_qualified_name="main",
                symbol_type=SymbolType.FUNCTION,
                language=Language.C,
                file_path="a.c",
                start_line=0,
            )


class TestFileRecord:
    def test_minimal_record(self) -> None:
        record = FileRecord(
            relative_path="src/main.py",
            filename="main.py",
            extension=".py",
            language=Language.PYTHON,
        )
        assert record.scan_status == ScanStatus.PENDING
        assert record.symbol_counts.total == 0

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FileRecord(
                relative_path="/abs/main.py",
                filename="main.py",
                extension=".py",
                language=Language.PYTHON,
            )


class TestIndexStatus:
    def test_status_model(self) -> None:
        status = IndexStatus(
            project_name="demo",
            project_root="/home/user/demo",
            index_version="1.0",
            indexed_file_count=3,
            indexed_symbol_count=42,
            health=IntegrityStatus.HEALTHY,
        )
        assert status.pending_files == 0
        assert status.failed_files == 0

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IndexStatus(
                project_name="demo",
                project_root="/home/user/demo",
                index_version="1.0",
                indexed_file_count=-1,
                indexed_symbol_count=0,
                health=IntegrityStatus.HEALTHY,
            )

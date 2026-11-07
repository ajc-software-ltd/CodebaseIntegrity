"""Tests for duplicate declaration detection (PLAN.md §10.4)."""

from cii.core.enums import FindingSeverity
from cii.database.models import FileRow, SymbolRow
from cii.integrity.duplicate_detector import detect_duplicates


def _file(path: str, language: str = "cpp") -> FileRow:
    return FileRow(
        file_id=1,
        project_id="p",
        relative_path=path,
        filename=path.rsplit("/", 1)[-1],
        extension="." + path.rsplit(".", 1)[-1],
        language=language,
    )


def _symbol(fqn: str, symbol_type: str = "class", fingerprint: str = "fp1",
            signature: str | None = None) -> SymbolRow:
    return SymbolRow(
        symbol_id=1,
        file_id=1,
        symbol_name=fqn.split("::")[-1],
        fully_qualified_name=fqn,
        symbol_type=symbol_type,
        fingerprint=fingerprint,
        signature=signature,
    )


class TestDuplicateDetector:
    def test_within_file_duplicate_is_error(self) -> None:
        findings = detect_duplicates([
            (_file("a.cpp"), [_symbol("f", "function"), _symbol("f", "function")]),
        ])
        assert [f.code for f in findings] == ["duplicate_declaration"]
        assert findings[0].severity is FindingSeverity.ERROR

    def test_header_source_pair_is_legitimate(self) -> None:
        findings = detect_duplicates([
            (_file("a.h"), [_symbol("f", "function")]),
            (_file("a.cpp"), [_symbol("f", "function")]),
        ])
        assert findings == []

    def test_definition_in_two_sources_is_error(self) -> None:
        findings = detect_duplicates([
            (_file("a.cpp"), [_symbol("f", "function")]),
            (_file("b.cpp"), [_symbol("f", "function")]),
        ])
        assert [f.code for f in findings] == ["duplicate_declaration"]

    def test_overloads_are_legitimate(self) -> None:
        findings = detect_duplicates([
            (_file("a.cpp"), [
                _symbol("f", "function", fingerprint="fp1"),
                _symbol("f", "function", fingerprint="fp2"),
            ]),
        ])
        assert findings == []

    def test_overloads_across_files_legitimate(self) -> None:
        findings = detect_duplicates([
            (_file("a.cpp"), [_symbol("f", "function", fingerprint="fp1")]),
            (_file("b.cpp"), [_symbol("f", "function", fingerprint="fp2")]),
        ])
        assert findings == []

    def test_conflicting_type_declarations_warn(self) -> None:
        findings = detect_duplicates([
            (_file("a.hpp"), [_symbol("C", "class", fingerprint="fp1")]),
            (_file("b.hpp"), [_symbol("C", "class", fingerprint="fp2")]),
        ])
        assert [f.code for f in findings] == ["conflicting_declaration"]
        assert findings[0].severity is FindingSeverity.WARNING

    def test_csharp_partial_class_is_legitimate(self) -> None:
        findings = detect_duplicates([
            (_file("a.cs", "csharp"), [
                _symbol("C", "class", fingerprint="fp1", signature="public class C")
            ]),
            (_file("b.cs", "csharp"), [
                _symbol("C", "class", fingerprint="fp2",
                        signature="public partial class C")
            ]),
        ])
        assert findings == []

    def test_python_cross_file_is_not_compared(self) -> None:
        findings = detect_duplicates([
            (_file("a.py", "python"), [_symbol("helper", "function")]),
            (_file("b.py", "python"), [_symbol("helper", "function")]),
        ])
        assert findings == []

"""Duplicate declaration detection (PLAN.md §10.4).

Findings distinguish legitimate patterns from suspicious ones and are never
acted upon automatically — the source code is not modified:

- the same function declared in a header and defined in a source file is a
  declaration/definition pair, not a duplicate;
- overloads (same name, different signatures) are legitimate;
- C# partial classes declared across files are legitimate;
- the same fully qualified type declared with conflicting shapes is a warning;
- the same definition present in multiple source files is an error;
- the same fingerprint repeated within one file is an error.

Policy per language: C/C++ cross-file comparisons use the header/source
distinction; Python fully qualified names are file-local, so cross-file Python
comparisons are not performed (they would produce systematic false positives).
"""

from collections import defaultdict
from collections.abc import Sequence

from cii.core.enums import FindingSeverity, Language, SymbolType
from cii.core.models import IntegrityFinding
from cii.database.models import FileRow, SymbolRow

_HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx"}
_SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx"}
_TYPE_LIKE = {
    SymbolType.CLASS.value,
    SymbolType.STRUCT.value,
    SymbolType.INTERFACE.value,
    SymbolType.RECORD.value,
    SymbolType.UNION.value,
    SymbolType.ENUM.value,
}


def detect_duplicates(
    rows_by_file: Sequence[tuple[FileRow, list[SymbolRow]]]
) -> list[IntegrityFinding]:
    """Analyse symbol rows grouped by file and return duplicate findings."""
    findings: list[IntegrityFinding] = []

    # (fqn, type, fingerprint) -> list[(file_row, symbol_row)]
    exact: dict[tuple[str, str, str], list[tuple[FileRow, SymbolRow]]] = defaultdict(list)
    # (fqn, type) -> distinct fingerprints and their files
    by_identity: dict[tuple[str, str], list[tuple[FileRow, SymbolRow]]] = defaultdict(list)

    for file_row, symbol_rows in rows_by_file:
        for symbol_row in symbol_rows:
            key = (
                symbol_row.fully_qualified_name,
                symbol_row.symbol_type,
                symbol_row.fingerprint or "",
            )
            exact[key].append((file_row, symbol_row))
            by_identity[key[:2]].append((file_row, symbol_row))

    for (fqn, symbol_type, fingerprint), entries in sorted(exact.items()):
        files = {file_row.relative_path for file_row, _ in entries}
        if len(files) < 2:
            if len(entries) > 1:
                findings.append(IntegrityFinding(
                    code="duplicate_declaration",
                    severity=FindingSeverity.ERROR,
                    message=f"{symbol_type} '{fqn}' declared {len(entries)} times in one file",
                    file_path=entries[0][0].relative_path,
                    symbol=fqn,
                ))
            continue
        if _is_legitimate_pair(entries):
            continue
        if symbol_type in _TYPE_LIKE and _has_partial_marker(entries):
            continue
        if _is_python(entries):
            continue  # Python FQNs are file-local — cross-file comparison is noise
        findings.append(IntegrityFinding(
            code="duplicate_declaration",
            severity=FindingSeverity.ERROR,
            message=(
                f"{symbol_type} '{fqn}' has identical definitions in "
                f"{len(files)} files: {', '.join(sorted(files))}"
            ),
            file_path=sorted(files)[0],
            symbol=fqn,
        ))

    for (fqn, symbol_type), entries in sorted(by_identity.items()):
        fingerprints = {symbol_row.fingerprint for _, symbol_row in entries}
        files = {file_row.relative_path for file_row, _ in entries}
        if len(fingerprints) <= 1 or len(files) < 2:
            continue
        if symbol_type in (SymbolType.FUNCTION.value, SymbolType.METHOD.value):
            continue  # differing signatures = legitimate overloads
        if _has_partial_marker(entries):
            continue
        if _is_python(entries):
            continue
        findings.append(IntegrityFinding(
            code="conflicting_declaration",
            severity=FindingSeverity.WARNING,
            message=(
                f"{symbol_type} '{fqn}' is declared with differing shapes in "
                f"{', '.join(sorted(files))}"
            ),
            file_path=sorted(files)[0],
            symbol=fqn,
        ))
    return findings


def _is_legitimate_pair(entries: list[tuple[FileRow, SymbolRow]]) -> bool:
    """Header declaration + source definition is not a duplicate (C/C++)."""
    suffixes = {file_row.extension for file_row, _ in entries}
    has_header = bool(suffixes & _HEADER_SUFFIXES)
    has_source = bool(suffixes & _SOURCE_SUFFIXES)
    non_cfamilies = {
        file_row.language for file_row, _ in entries
        if file_row.language not in (Language.C.value, Language.CPP.value)
    }
    return has_header and has_source and not non_cfamilies


def _has_partial_marker(entries: list[tuple[FileRow, SymbolRow]]) -> bool:
    """C# partial classes may legitimately span files."""
    return any(
        "partial" in (symbol_row.signature or "").split()
        for _, symbol_row in entries
    )


def _is_python(entries: list[tuple[FileRow, SymbolRow]]) -> bool:
    """Python fully qualified names are file-local — never compare across files."""
    return any(file_row.language == Language.PYTHON.value for file_row, _ in entries)

"""Integrity validation (PLAN.md §10).

Read-only verification that the stored structural index matches the actual
source code. Deterministic — no LLM interpretation involved. Findings are
evidence for investigation; validation never modifies source files or index
records.

Quick validation covers database consistency, filesystem reconciliation,
duplicate declarations and Markdown freshness. ``full_scan=True`` additionally
re-parses every indexed file and compares parser output against the stored
symbols (missing/new symbols, unresolved relationships).
"""

import time
from pathlib import Path

from cii.core.configuration import CiiConfig
from cii.core.enums import FindingSeverity, Language, ScanStatus
from cii.core.models import IntegrityFinding
from cii.database.database import Database
from cii.database.models import FileRow, SymbolRow
from cii.database.repositories import (
    FileRepository,
    IntegrityReportRepository,
    ProjectRepository,
    SymbolRepository,
)
from cii.indexer.markdown_exporter import is_index_current
from cii.indexer.symbol_resolver import resolve_target
from cii.integrity.consistency_checker import check_database, check_index_rows
from cii.integrity.duplicate_detector import detect_duplicates
from cii.integrity.health import HealthSummary, summarise
from cii.integrity.reconciliation import reconcile
from cii.parsers.registry import ParserRegistry, default_registry
from cii.utilities.paths import require_within_root


class Validator:
    """Produces integrity findings for one project."""

    def __init__(
        self,
        project_root: Path,
        config: CiiConfig,
        database: Database,
        registry: ParserRegistry | None = None,
    ) -> None:
        self._project_root = project_root
        self._config = config
        self._database = database
        self._registry = registry or default_registry()

    def validate(self, *, full_scan: bool = False) -> HealthSummary:
        """Run validation and persist an integrity report row.

        Raises:
            ProjectRootError: the project is not registered.
        """
        started = time.time()
        project = ProjectRepository(self._database.connection).get_by_root(
            str(self._project_root)
        )
        if project is None:
            from cii.core.exceptions import ProjectRootError

            raise ProjectRootError(
                f"project not registered in CII: {self._project_root} (run 'cii init')"
            )

        findings: list[IntegrityFinding] = []
        files_checked = 0
        try:
            findings.extend(check_database(self._database))
            findings.extend(check_index_rows(self._database, project.project_id))

            files = FileRepository(self._database.connection).list_all(project.project_id)
            files_checked = len(files)
            findings.extend(self._reconciliation_findings())
            findings.extend(self._duplicate_findings(files))
            findings.extend(self._markdown_findings())

            if full_scan:
                findings.extend(self._full_scan_findings(project.project_id, files))

            summary = summarise(
                findings,
                files_checked=files_checked,
                validation_time=time.time() - started,
                full_scan=full_scan,
            )
        except Exception as error:  # validation failure itself
            summary = summarise(
                [
                    IntegrityFinding(
                        code="validation_failed",
                        severity=FindingSeverity.ERROR,
                        message=f"validation could not complete: {error}",
                    )
                ],
                files_checked=files_checked,
                validation_time=time.time() - started,
                full_scan=full_scan,
                failed=True,
            )

        IntegrityReportRepository(self._database.connection).add(
            project.project_id,
            summary.status.value,
            files_checked=summary.files_checked,
            errors_found=summary.errors,
            warnings_found=summary.warnings,
        )
        return summary

    def _reconciliation_findings(self) -> list[IntegrityFinding]:
        findings: list[IntegrityFinding] = []
        changes = reconcile(self._project_root, self._config, self._database)
        for record in changes.added:
            findings.append(IntegrityFinding(
                code="unindexed_file",
                severity=FindingSeverity.WARNING,
                message="eligible source file is not in the index",
                file_path=record.relative_path,
            ))
        for record in changes.modified:
            findings.append(IntegrityFinding(
                code="changed_hash",
                severity=FindingSeverity.WARNING,
                message="file content differs from the indexed fingerprint",
                file_path=record.relative_path,
            ))
        for relative_path in changes.deleted:
            findings.append(IntegrityFinding(
                code="missing_file",
                severity=FindingSeverity.WARNING,
                message="indexed file no longer exists on disk",
                file_path=relative_path,
            ))
        for rename in changes.renamed:
            findings.append(IntegrityFinding(
                code="renamed_file",
                severity=FindingSeverity.WARNING,
                message=(
                    f"file moved from {rename.old_relative_path} to "
                    f"{rename.new_relative_path} (matching content hash)"
                ),
                file_path=rename.new_relative_path,
            ))
        return findings

    def _duplicate_findings(self, files: list[FileRow]) -> list[IntegrityFinding]:
        symbol_repo = SymbolRepository(self._database.connection)
        rows_by_file = [
            (file_row, symbol_repo.list_by_file(int(file_row.file_id)))
            for file_row in files
            if file_row.file_id is not None
        ]
        return detect_duplicates(rows_by_file)

    def _markdown_findings(self) -> list[IntegrityFinding]:
        current = is_index_current(self._database, self._project_root, self._config)
        if current is None:
            return [IntegrityFinding(
                code="stale_markdown",
                severity=FindingSeverity.WARNING,
                message="generated Markdown index is missing (run 'cii export')",
            )]
        if not current:
            return [IntegrityFinding(
                code="stale_markdown",
                severity=FindingSeverity.WARNING,
                message="generated Markdown index does not match the database",
            )]
        return []

    def _full_scan_findings(
        self, project_id: str, files: list[FileRow]
    ) -> list[IntegrityFinding]:
        """Re-parse indexed files and compare parser output with stored symbols."""
        findings: list[IntegrityFinding] = []
        symbol_repo = SymbolRepository(self._database.connection)
        all_rows = symbol_repo.list_for_project(project_id)
        for file_row in files:
            if file_row.scan_status != ScanStatus.INDEXED.value or file_row.file_id is None:
                continue
            parser = self._registry.get(Language(file_row.language))
            if parser is None:
                continue
            absolute = require_within_root(
                self._project_root / file_row.relative_path, self._project_root
            )
            result = parser.parse(absolute, file_row.relative_path)
            if not result.ok:
                findings.append(IntegrityFinding(
                    code="parser_failure",
                    severity=FindingSeverity.WARNING,
                    message="re-parse during full validation failed",
                    file_path=file_row.relative_path,
                ))
                continue
            stored = {
                (row.fully_qualified_name, row.symbol_type, row.fingerprint or "")
                for row in symbol_repo.list_by_file(int(file_row.file_id))
            }
            parsed = {
                (symbol.fully_qualified_name, symbol.symbol_type.value,
                 symbol.fingerprint or "")
                for symbol in result.symbols
            }
            for identity in sorted(stored - parsed):
                findings.append(IntegrityFinding(
                    code="missing_symbols",
                    severity=FindingSeverity.WARNING,
                    message=f"indexed symbol '{identity[0]}' is no longer in the source",
                    file_path=file_row.relative_path,
                    symbol=identity[0],
                ))
            for identity in sorted(parsed - stored):
                findings.append(IntegrityFinding(
                    code="new_symbols",
                    severity=FindingSeverity.WARNING,
                    message=f"symbol '{identity[0]}' exists in source but not in the index",
                    file_path=file_row.relative_path,
                    symbol=identity[0],
                ))
            findings.extend(self._unresolved_reference_findings(result.references, all_rows))
        return findings

    def _unresolved_reference_findings(
        self, references, all_rows: list[SymbolRow]
    ) -> list[IntegrityFinding]:
        findings: list[IntegrityFinding] = []
        seen: set[str] = set()
        for reference in references:
            if reference.target_name in seen:
                continue
            if resolve_target(reference.target_name, all_rows) is None:
                seen.add(reference.target_name)
                findings.append(IntegrityFinding(
                    code="unresolved_relationship",
                    severity=FindingSeverity.WARNING,
                    message=(
                        f"relationship target '{reference.target_name}' "
                        f"({reference.relationship_type.value}) does not resolve "
                        "to an indexed symbol"
                    ),
                    symbol=reference.source_fqn,
                ))
        return findings

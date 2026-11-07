"""Database row models.

These models mirror the SQLite schema (PLAN.md §6.2) exactly, including
surrogate keys. Domain-facing models live in :mod:`cii.core.models`;
repositories convert between the two layers.
"""

from pydantic import BaseModel, Field


class ProjectRow(BaseModel):
    project_id: str
    project_name: str
    project_root: str
    created_at: float
    last_scan: float | None = None
    index_version: str
    configuration_hash: str


class FileRow(BaseModel):
    file_id: int | None = None
    project_id: str
    relative_path: str
    filename: str
    extension: str
    language: str
    content_hash: str | None = None
    file_size: int | None = None
    modified_at: float | None = None
    last_scanned: float | None = None
    scan_status: str = "pending"
    parser_version: str | None = None


class SymbolRow(BaseModel):
    symbol_id: int | None = None
    file_id: int | None = None
    parent_symbol_id: int | None = None
    symbol_name: str
    fully_qualified_name: str
    symbol_type: str
    visibility: str = "unknown"
    signature: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    fingerprint: str | None = None


class NamespaceRow(BaseModel):
    namespace_id: int | None = None
    file_id: int | None = None
    namespace_name: str
    parent_namespace_id: int | None = None


class NamespaceInput(BaseModel):
    """Input for namespace replacement: a declaration with a name-level parent."""

    namespace_name: str = Field(min_length=1)
    parent_name: str | None = None


class RelationshipRow(BaseModel):
    relationship_id: int | None = None
    source_symbol_id: int
    target_symbol_id: int
    relationship_type: str
    confidence: float = 1.0
    resolution_status: str = "resolved"


class ScanHistoryRow(BaseModel):
    scan_id: int | None = None
    project_id: str
    scan_type: str
    started_at: float
    completed_at: float | None = None
    files_processed: int = 0
    files_failed: int = 0
    symbols_added: int = 0
    symbols_updated: int = 0
    symbols_removed: int = 0
    status: str = "running"


class IntegrityReportRow(BaseModel):
    report_id: int | None = None
    project_id: str
    validation_time: float
    files_checked: int = 0
    errors_found: int = 0
    warnings_found: int = 0
    report_status: str


class HealthReport(BaseModel):
    """Result of a database health check."""

    ok: bool
    schema_version: int
    journal_mode: str
    integrity_check: str
    foreign_key_violations: int = Field(ge=0)
    error: str | None = None

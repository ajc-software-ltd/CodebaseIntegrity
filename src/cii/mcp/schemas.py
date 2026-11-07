"""MCP tool result schemas (PLAN.md §12.1).

Output models for the nine CII tools. They are serialised to JSON for tool
responses, so field names are part of the MCP interface.
"""

from pydantic import BaseModel, Field

from cii.search.relationship_search import RelationshipHit
from cii.search.symbol_search import SymbolSearchHit


class IndexStatusTool(BaseModel):
    project_name: str
    project_root: str
    index_version: str
    indexed_file_count: int
    indexed_symbol_count: int
    last_successful_scan: float | None = None
    pending_files: int = 0
    failed_files: int = 0
    files_by_status: dict[str, int] = Field(default_factory=dict)
    health: str = "unknown"
    last_validation_status: str | None = None


class IndexSearchTool(BaseModel):
    total: int
    offset: int
    limit: int
    results: list[SymbolSearchHit]


class IndexSymbolTool(BaseModel):
    query: str
    total: int
    results: list[SymbolSearchHit]


class IndexScanTool(BaseModel):
    scan_id: int
    status: str = "completed"
    mode: str = "incremental"
    path: str | None = None
    added: int = 0
    modified: int = 0
    deleted: int = 0
    renamed: int = 0
    unchanged: int = 0
    files_indexed: int = 0
    files_failed: int = 0
    symbols_added: int = 0
    symbols_updated: int = 0
    symbols_removed: int = 0


class IndexRebuildTool(BaseModel):
    status: str = "completed"
    scan_id: int
    backup_path: str
    files_indexed: int = 0
    symbols_indexed: int = 0


class IndexValidateTool(BaseModel):
    status: str
    errors: int
    warnings: int
    files_checked: int
    full_scan: bool
    findings: list[dict] = Field(default_factory=list)


class IndexDependenciesTool(BaseModel):
    symbol: str
    total: int
    results: list[RelationshipHit]


class ScanHistoryEntry(BaseModel):
    scan_id: int
    scan_type: str
    started_at: float
    completed_at: float | None = None
    duration_seconds: float | None = None
    files_processed: int = 0
    symbols_added: int = 0
    status: str


class IndexStatisticsTool(BaseModel):
    total_files: int
    files_by_language: dict[str, int] = Field(default_factory=dict)
    total_symbols: int
    symbols_by_type: dict[str, int] = Field(default_factory=dict)
    namespaces: int = 0
    parser_failures: int = 0
    recent_scans: list[ScanHistoryEntry] = Field(default_factory=list)

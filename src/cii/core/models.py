"""Core domain models.

These are the in-memory representations of structural information. The SQLite
layer (Milestone 02) maps rows onto these models; the MCP layer (Milestone 09)
serialises them into tool responses.

Identity rules (PLAN.md §5.4): a symbol is identified by project + file +
fully qualified name + symbol type + parent. Line numbers are navigational
metadata only and never form part of identity.
"""

import hashlib

from pydantic import BaseModel, Field, field_validator

from cii.core.enums import IntegrityStatus, Language, ScanStatus, SymbolType, Visibility
from cii.utilities.paths import validate_relative_path


class NamespaceInput(BaseModel):
    """A namespace declaration extracted from one file (input for storage).

    Used by the parser layer (extraction) and the database layer (persistence);
    parent links are name-based and resolved at insertion time.
    """

    namespace_name: str = Field(min_length=1)
    parent_name: str | None = None


class SymbolCounts(BaseModel):
    """Per-file symbol counts.

    Counts are always derived from extracted symbols, never entered manually.
    """

    namespaces: int = Field(default=0, ge=0)
    classes: int = Field(default=0, ge=0)
    structures: int = Field(default=0, ge=0)
    interfaces: int = Field(default=0, ge=0)
    enums: int = Field(default=0, ge=0)
    functions: int = Field(default=0, ge=0)
    methods: int = Field(default=0, ge=0)
    properties: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        """Total number of counted symbols."""
        return (
            self.namespaces
            + self.classes
            + self.structures
            + self.interfaces
            + self.enums
            + self.functions
            + self.methods
            + self.properties
        )


class SymbolInfo(BaseModel):
    """A single extracted programming symbol."""

    name: str = Field(min_length=1)
    fully_qualified_name: str = Field(min_length=1)
    symbol_type: SymbolType
    language: Language
    file_path: str
    parent: str | None = None
    namespace: str | None = None
    visibility: Visibility = Visibility.UNKNOWN
    signature: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    fingerprint: str | None = None

    @field_validator("file_path")
    @classmethod
    def _file_path_is_relative(cls, value: str) -> str:
        """Symbol file paths are always project-relative POSIX paths."""
        return validate_relative_path(value)


class FileRecord(BaseModel):
    """An indexed source file and its scan state."""

    relative_path: str
    filename: str
    extension: str
    language: Language
    content_hash: str | None = None
    file_size: int | None = Field(default=None, ge=0)
    modified_at: float | None = None
    last_scanned: float | None = None
    scan_status: ScanStatus = ScanStatus.PENDING
    parser_version: str | None = None
    symbol_counts: SymbolCounts = Field(default_factory=SymbolCounts)

    @field_validator("relative_path")
    @classmethod
    def _relative_path_is_relative(cls, value: str) -> str:
        return validate_relative_path(value)


class IndexStatus(BaseModel):
    """Project-level index health snapshot (MCP tool `index_status`)."""

    project_name: str
    project_root: str
    index_version: str
    indexed_file_count: int = Field(ge=0)
    indexed_symbol_count: int = Field(ge=0)
    last_successful_scan: float | None = None
    pending_files: int = Field(default=0, ge=0)
    failed_files: int = Field(default=0, ge=0)
    health: IntegrityStatus


def symbol_fingerprint(symbol_type: SymbolType, fully_qualified_name: str,
                       signature: str | None) -> str:
    """Stable identity fingerprint for a symbol (PLAN.md §5.4).

    SHA-256 over symbol type, fully qualified name and signature (when
    available). Line numbers are deliberately excluded: they move when source
    is edited and never form part of identity.
    """
    payload = f"{symbol_type.value}|{fully_qualified_name}|{signature or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

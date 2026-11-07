"""Parser contract.

Every language parser implements :class:`BaseParser` and returns the same
internal representation (:class:`ParseResult`), so the indexer and database
layers are language-independent (PLAN.md §8.1).

Failure handling (PLAN.md §8.4): a parser never deletes previous index
information. ``ParseResult.ok`` is False only when nothing trustworthy could
be extracted (I/O failure, undecodable content, syntax errors); partial but
usable trees still extract symbols and record issues, which are reported
rather than silently ignored.
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from cii.core.enums import Language, RelationshipType
from cii.core.models import NamespaceInput, SymbolInfo

_MAX_SIGNATURE_LENGTH = 300


class SymbolReference(BaseModel):
    """Parser evidence of a structural relationship (PLAN.md §6.2).

    ``target_name`` is a type name as written in the source; the indexer
    resolves it to a symbol id where possible. Relationships are recorded only
    with this kind of parser or semantic-analysis evidence behind them.
    """

    source_fqn: str
    target_name: str
    relationship_type: RelationshipType
    confidence: float = Field(default=1.0, gt=0.0, le=1.0)


class ParseIssue(BaseModel):
    """A reported parse problem (PLAN.md §8.4)."""

    file_path: str
    parser: str
    reason: str
    parser_version: str
    timestamp: float


class ParseResult(BaseModel):
    """Uniform parser output."""

    file_path: str
    language: Language
    parser_name: str
    parser_version: str
    ok: bool = True
    symbols: list[SymbolInfo] = []
    namespaces: list[NamespaceInput] = []
    references: list[SymbolReference] = []
    issues: list[ParseIssue] = []


class BaseParser(ABC):
    """Contract every language parser must follow."""

    @abstractmethod
    def get_language(self) -> Language:
        """The language this parser instance extracts."""

    @abstractmethod
    def get_parser_name(self) -> str:
        """Stable parser identifier (recorded on indexed files)."""

    @abstractmethod
    def get_parser_version(self) -> str:
        """Parser implementation version (recorded on indexed files)."""

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Whether this parser can handle the given file."""

    @abstractmethod
    def parse(self, file_path: Path, relative_path: str) -> ParseResult:
        """Extract structural symbols from one file.

        Never raises for content problems: failures are reported inside the
        result (``ok=False`` plus issues) so callers can retain previous
        index information.
        """


def normalise_signature(text: str) -> str:
    """Collapse a declaration to a single whitespace-normalised line."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) > _MAX_SIGNATURE_LENGTH:
        return collapsed[: _MAX_SIGNATURE_LENGTH - 1] + "…"
    return collapsed

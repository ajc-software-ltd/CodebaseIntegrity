"""Data-file parser (JSON, XML, plain text).

Data formats have no classes, functions or namespaces to extract. They are
still worth *tracking*: the index answers "what exists and where" for
configuration and data files too. This parser records the file with zero
structural symbols — honest indexing, healthy validation.
"""

from importlib.metadata import version as package_version
from pathlib import Path

from cii.core.enums import Language
from cii.parsers.base import BaseParser, ParseResult

_SUFFIXES = {
    Language.JSON: {".json", ".jsonl"},
    Language.XML: {".xml"},
    Language.TEXT: {".txt"},
}
_PARSER_NAME = "cii-data-tracker"


class DataParser(BaseParser):
    """Presence-tracking parser for data formats (no structural symbols)."""

    def __init__(self, language: Language) -> None:
        if language not in _SUFFIXES:
            raise ValueError(f"DataParser does not support {language}")
        self._language = language

    def get_language(self) -> Language:
        return self._language

    def get_parser_name(self) -> str:
        return _PARSER_NAME

    def get_parser_version(self) -> str:
        try:
            return package_version("codebase-integrity")
        except Exception:
            return "unknown"

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in _SUFFIXES[self._language]

    def parse(self, file_path: Path, relative_path: str) -> ParseResult:
        # Data files carry no structural symbols; recording the file itself
        # is the complete index for them.
        return ParseResult(
            file_path=relative_path,
            language=self._language,
            parser_name=_PARSER_NAME,
            parser_version=self.get_parser_version(),
            ok=True,
        )

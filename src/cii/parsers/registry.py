"""Parser registry.

Maps languages to parser instances so the scanner/indexer can obtain the
right extractor without depending on concrete parser classes. New languages
are added by registering another :class:`BaseParser` — the database and MCP
interfaces do not change (PLAN.md §8.3).
"""

from pathlib import Path

from cii.core.enums import Language
from cii.parsers.base import BaseParser
from cii.parsers.cpp.parser import CFamilyParser
from cii.parsers.csharp.parser import CSharpParser
from cii.parsers.python.parser import PythonParser


class ParserRegistry:
    """Language → parser lookup."""

    def __init__(self, parsers: list[BaseParser]) -> None:
        self._parsers: dict[Language, BaseParser] = {}
        for parser in parsers:
            self._parsers[parser.get_language()] = parser

    def get(self, language: Language) -> BaseParser | None:
        return self._parsers.get(language)

    def get_for_file(self, file_path: Path) -> BaseParser | None:
        for parser in self._parsers.values():
            if parser.supports(file_path):
                return parser
        return None

    def languages(self) -> list[Language]:
        return sorted(self._parsers, key=lambda language: language.value)


def default_registry() -> ParserRegistry:
    """Registry with the v0.1 language set (C, C++, C#, Python)."""
    return ParserRegistry([
        CFamilyParser(Language.C),
        CFamilyParser(Language.CPP),
        CSharpParser(),
        PythonParser(),
    ])

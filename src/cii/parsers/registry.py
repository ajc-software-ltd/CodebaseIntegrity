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
from cii.parsers.data import DataParser
from cii.parsers.python.parser import PythonParser
from cii.parsers.treesitter.generic import SpecParser
from cii.parsers.treesitter.specs import NEW_LANGUAGE_SPECS


class ParserRegistry:
    """Language → parser lookup."""

    def __init__(self, parsers: list[BaseParser]) -> None:
        self._parsers: dict[Language, BaseParser] = {}
        for parser in parsers:
            self._parsers[parser.get_language()] = parser

    def get(self, language: Language) -> BaseParser | None:
        return self._parsers.get(language)

    def get_for_file(self, file_path: Path) -> BaseParser | None:
        # exact file names win over extensions (same precedence as the scanner)
        from cii.core.configuration import DEFAULT_FILENAMES

        by_name = DEFAULT_FILENAMES.get(file_path.name)
        if by_name is not None:
            return self.get(Language(by_name))
        for parser in self._parsers.values():
            if parser.supports(file_path):
                return parser
        return None

    def languages(self) -> list[Language]:
        return sorted(self._parsers, key=lambda language: language.value)


def default_registry() -> ParserRegistry:
    """Registry with every supported language (PLAN.md sec 8.2-8.3).

    GLSL/HLSL reuse the C-family extractor (C-shaped grammars); the extended
    set (JavaScript, TypeScript, Rust, Java, Go, Lua, CMake) runs through the
    spec-driven extractor.
    """
    return ParserRegistry([
        CFamilyParser(Language.C),
        CFamilyParser(Language.CPP),
        CFamilyParser(Language.GLSL),
        CFamilyParser(Language.HLSL),
        CSharpParser(),
        PythonParser(),
        DataParser(Language.JSON),
        DataParser(Language.XML),
        DataParser(Language.TEXT),
        *(SpecParser(spec) for spec in NEW_LANGUAGE_SPECS),
    ])

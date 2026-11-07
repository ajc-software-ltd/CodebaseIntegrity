"""Parser registry tests."""

from pathlib import Path

from cii.core.enums import Language
from cii.parsers.cpp.parser import CFamilyParser
from cii.parsers.registry import ParserRegistry, default_registry


class TestRegistry:
    def test_default_registry_covers_v01_languages(self) -> None:
        registry = default_registry()
        assert registry.languages() == [
            Language.C, Language.CPP, Language.CSHARP, Language.PYTHON,
        ]

    def test_get_by_language(self) -> None:
        registry = default_registry()
        assert isinstance(registry.get(Language.CPP), CFamilyParser)
        assert registry.get(Language.UNKNOWN) is None

    def test_get_for_file(self) -> None:
        registry = default_registry()
        assert registry.get_for_file(Path("a.cpp")).get_language() is Language.CPP
        assert registry.get_for_file(Path("a.cs")).get_language() is Language.CSHARP
        assert registry.get_for_file(Path("a.py")).get_language() is Language.PYTHON
        assert registry.get_for_file(Path("image.png")) is None

    def test_custom_registry(self) -> None:
        registry = ParserRegistry([CFamilyParser(Language.C)])
        assert registry.languages() == [Language.C]
        assert registry.get(Language.CPP) is None

    def test_parser_supports(self) -> None:
        registry = default_registry()
        cpp_parser = registry.get(Language.CPP)
        assert cpp_parser.supports(Path("x/Hpp.hpp")) is True
        assert cpp_parser.supports(Path("x/main.c")) is False

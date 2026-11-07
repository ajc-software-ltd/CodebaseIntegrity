"""Tree-sitter grammar registry.

Loads the compiled grammar for a language lazily and caches the parser
instances. Grammar packages:

- ``tree-sitter-c``        → C
- ``tree-sitter-cpp``      → C++
- ``tree-sitter-c-sharp``  → C#
"""

from functools import lru_cache

import tree_sitter

from cii.core.enums import Language
from cii.core.exceptions import CiiError


class GrammarError(CiiError):
    """A tree-sitter grammar could not be loaded."""


@lru_cache(maxsize=None)
def load_language(language: Language) -> tree_sitter.Language:
    """Return the tree-sitter Language object for a C-family language."""
    try:
        if language is Language.C:
            import tree_sitter_c as grammar
        elif language is Language.CPP:
            import tree_sitter_cpp as grammar
        elif language is Language.CSHARP:
            import tree_sitter_c_sharp as grammar
        else:
            raise GrammarError(f"no tree-sitter grammar registered for {language}")
        return tree_sitter.Language(grammar.language())
    except ImportError as error:
        raise GrammarError(f"grammar package missing for {language}: {error}") from error


@lru_cache(maxsize=None)
def load_parser(language: Language) -> tree_sitter.Parser:
    """Return a cached tree-sitter Parser bound to the language's grammar."""
    return tree_sitter.Parser(load_language(language))

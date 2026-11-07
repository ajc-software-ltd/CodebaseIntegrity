"""Tree-sitter grammar registry.

Loads the compiled grammar for a language lazily and caches the parser
instances. Grammar packages:

Grammar packages (PLAN.md sec 8.2-8.3 languages):
``tree-sitter-{c,cpp,c-sharp,javascript,typescript,rust,java,go,lua,glsl,hlsl,cmake}``.
"""

from functools import lru_cache

import tree_sitter

from cii.core.enums import Language
from cii.core.exceptions import CiiError


class GrammarError(CiiError):
    """A tree-sitter grammar could not be loaded."""


_GRAMMAR_MODULES = {
    Language.C: "tree_sitter_c",
    Language.CPP: "tree_sitter_cpp",
    Language.CSHARP: "tree_sitter_c_sharp",
    Language.JAVASCRIPT: "tree_sitter_javascript",
    Language.TYPESCRIPT: "tree_sitter_typescript",
    Language.RUST: "tree_sitter_rust",
    Language.JAVA: "tree_sitter_java",
    Language.GO: "tree_sitter_go",
    Language.LUA: "tree_sitter_lua",
    Language.GLSL: "tree_sitter_glsl",
    Language.HLSL: "tree_sitter_hlsl",
    Language.CMAKE: "tree_sitter_cmake",
}


@lru_cache(maxsize=None)
def load_language(language: Language) -> tree_sitter.Language:
    """Return the tree-sitter Language object for a supported language."""
    import importlib

    module_name = _GRAMMAR_MODULES.get(language)
    if module_name is None:
        raise GrammarError(f"no tree-sitter grammar registered for {language}")
    try:
        grammar = importlib.import_module(module_name)
    except ImportError as error:
        raise GrammarError(f"grammar package missing for {language}: {error}") from error
    loader = getattr(grammar, "language", None)
    if loader is None:  # e.g. tree_sitter_typescript exposes language_typescript
        candidates = [name for name in dir(grammar) if name.startswith("language")]
        if not candidates:
            raise GrammarError(f"grammar module {module_name} exposes no language()")
        loader = getattr(grammar, candidates[0])
    return tree_sitter.Language(loader())


@lru_cache(maxsize=None)
def load_parser(language: Language) -> tree_sitter.Parser:
    """Return a cached tree-sitter Parser bound to the language's grammar."""
    return tree_sitter.Parser(load_language(language))

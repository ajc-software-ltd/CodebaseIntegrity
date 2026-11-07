"""Python structural extraction (standard-library ``ast``).

Extraction categories (PLAN.md §8.2):
- classes (nested classes supported), with base classes as inherits evidence
- functions at module scope and nested inside functions
- methods (inside classes), constructors (__init__), destructors (__del__)
- properties (@property), with static/class methods flagged by their
  decorators in the signature
- decorators are part of the recorded signature

Modules are represented by the file record itself (each Python file is one
module), so no separate module symbol is fabricated. Syntax errors are
reported as issues with ``ok=False`` — previous index information must be
retained by the caller (PLAN.md §8.4).
"""

import ast
import time
from pathlib import Path

from cii.core.enums import Language, RelationshipType, SymbolType, Visibility
from cii.core.models import SymbolInfo, symbol_fingerprint
from cii.parsers.base import (
    BaseParser,
    ParseIssue,
    ParseResult,
    SymbolReference,
    normalise_signature,
)

_SUFFIXES = {".py", ".pyi"}
_PARSER_NAME = "python-ast"
_SEPARATOR = "."


class PythonParser(BaseParser):
    """Structural extractor for Python source files."""

    def get_language(self) -> Language:
        return Language.PYTHON

    def get_parser_name(self) -> str:
        return _PARSER_NAME

    def get_parser_version(self) -> str:
        import platform

        return f"cpython-{platform.python_version()}"

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in _SUFFIXES

    def parse(self, file_path: Path, relative_path: str) -> ParseResult:
        parser_version = self.get_parser_version()
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            return self._failure(relative_path, parser_version, f"read failed: {error}")
        try:
            tree = ast.parse(content)
        except SyntaxError as error:
            return self._failure(
                relative_path, parser_version,
                f"syntax error at line {error.lineno}: {error.msg}",
            )

        symbols: list[SymbolInfo] = []
        references: list[SymbolReference] = []
        self._walk_body(
            tree.body,
            relative_path,
            prefix="",
            parent=None,
            in_class=False,
            symbols=symbols,
            references=references,
        )
        return ParseResult(
            file_path=relative_path,
            language=Language.PYTHON,
            parser_name=_PARSER_NAME,
            parser_version=parser_version,
            ok=True,
            symbols=symbols,
            namespaces=[],  # Python modules are represented by file records
            references=references,
            issues=[],
        )

    def _failure(self, relative_path: str, parser_version: str, reason: str) -> ParseResult:
        return ParseResult(
            file_path=relative_path,
            language=Language.PYTHON,
            parser_name=_PARSER_NAME,
            parser_version=parser_version,
            ok=False,
            issues=[ParseIssue(
                file_path=relative_path, parser=_PARSER_NAME, reason=reason,
                parser_version=parser_version, timestamp=time.time(),
            )],
        )

    def _walk_body(
        self,
        body: list[ast.stmt],
        relative_path: str,
        *,
        prefix: str,
        parent: str | None,
        in_class: bool,
        symbols: list[SymbolInfo],
        references: list[SymbolReference],
    ) -> None:
        for statement in body:
            if isinstance(statement, ast.ClassDef):
                self._handle_class(
                    statement, relative_path,
                    prefix=prefix, parent=parent, symbols=symbols,
                    references=references,
                )
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._handle_function(
                    statement, relative_path,
                    prefix=prefix, parent=parent, in_class=in_class,
                    symbols=symbols, references=references,
                )

    def _handle_class(
        self,
        node: ast.ClassDef,
        relative_path: str,
        *,
        prefix: str,
        parent: str | None,
        symbols: list[SymbolInfo],
        references: list[SymbolReference],
    ) -> None:
        fqn = f"{prefix}{_SEPARATOR}{node.name}" if prefix else node.name
        bases = [ast.unparse(base) for base in node.bases]
        class_text = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
        signature = normalise_signature(_decorators(node) + class_text)
        symbols.append(SymbolInfo(
            name=node.name,
            fully_qualified_name=fqn,
            symbol_type=SymbolType.CLASS,
            language=Language.PYTHON,
            file_path=relative_path,
            parent=parent,
            namespace=None,
            visibility=Visibility.UNKNOWN,
            signature=signature or None,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            fingerprint=symbol_fingerprint(SymbolType.CLASS, fqn, signature),
        ))
        for base_name in bases:
            references.append(SymbolReference(
                source_fqn=fqn,
                target_name=base_name,
                relationship_type=RelationshipType.INHERITS,
            ))
        self._walk_body(
            node.body,
            relative_path,
            prefix=fqn,
            parent=fqn,
            in_class=True,
            symbols=symbols,
            references=references,
        )

    def _handle_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        relative_path: str,
        *,
        prefix: str,
        parent: str | None,
        in_class: bool,
        symbols: list[SymbolInfo],
        references: list[SymbolReference],
    ) -> None:
        fqn = f"{prefix}{_SEPARATOR}{node.name}" if prefix else node.name
        if not in_class:
            symbol_type = SymbolType.FUNCTION
        elif node.name == "__init__":
            symbol_type = SymbolType.CONSTRUCTOR
        elif node.name == "__del__":
            symbol_type = SymbolType.DESTRUCTOR
        elif _has_property_decorator(node):
            symbol_type = SymbolType.PROPERTY
        else:
            symbol_type = SymbolType.METHOD

        arguments = ast.unparse(node.args)
        returns = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
        async_prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        signature = normalise_signature(
            _decorators(node) + f"{async_prefix}def {node.name}({arguments}){returns}"
        )
        symbols.append(SymbolInfo(
            name=node.name,
            fully_qualified_name=fqn,
            symbol_type=symbol_type,
            language=Language.PYTHON,
            file_path=relative_path,
            parent=parent,
            namespace=None,
            visibility=Visibility.UNKNOWN,
            signature=signature or None,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            fingerprint=symbol_fingerprint(symbol_type, fqn, signature),
        ))
        # Nested functions and classes belong to this function's scope.
        self._walk_body(
            node.body,
            relative_path,
            prefix=fqn,
            parent=fqn,
            in_class=False,
            symbols=symbols,
            references=references,
        )


def _decorators(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts = [f"@{ast.unparse(decorator)}" for decorator in node.decorator_list]
    return (" ".join(parts) + " ") if parts else ""


def _has_property_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "property":
            return True
    return False

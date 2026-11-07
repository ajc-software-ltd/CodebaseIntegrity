"""C and C++ structural extraction (tree-sitter).

One extractor family for both languages (PLAN.md §8.2): C++ adds namespaces,
classes, constructors/destructors, templates and inheritance; C contributes
structs, unions, enums and typedefs. The grammars differ, so
:class:`CFamilyParser` is instantiated once per language.

Extraction categories (verified against the grammars):
- namespace_definition → namespace declarations (nested components expanded)
- class/struct/union/enum_specifier → types (nested types supported)
- function_definition and function-declarator declarations → functions,
  methods, constructors (name == class name), destructors (destructor_name)
- template_declaration is transparent; the template head joins the signature
- base_class_clause → inherits relationships (parser evidence)
- access_specifier tracking → member visibility

Not extracted (outside the v0.1 spec): fields, enum members, global variables.
"""

import time
from importlib.metadata import version
from pathlib import Path

import tree_sitter

from cii.core.enums import Language, RelationshipType, SymbolType, Visibility
from cii.core.models import NamespaceInput, SymbolInfo, symbol_fingerprint
from cii.parsers.base import BaseParser, ParseIssue, ParseResult, SymbolReference
from cii.parsers.treesitter.language_registry import load_parser
from cii.parsers.treesitter.parser import (
    count_error_nodes,
    declaration_signature,
    field,
    node_text,
)

_SEPARATOR = "::"
_SUFFIXES = {
    Language.C: {".c"},
    Language.CPP: {".h", ".hh", ".hpp", ".hxx", ".cc", ".cpp", ".cxx"},
    # GLSL/HLSL grammars produce C-shaped trees (translation_unit,
    # struct_specifier, function_definition) and share this extractor.
    Language.GLSL: {".glsl", ".vert", ".frag", ".tesc", ".tese", ".geom", ".comp"},
    Language.HLSL: {".hlsl", ".fx", ".fxh"},
}
_PARSER_NAMES = {
    Language.C: "tree-sitter-c",
    Language.CPP: "tree-sitter-cpp",
    Language.GLSL: "tree-sitter-glsl",
    Language.HLSL: "tree-sitter-hlsl",
}

_METHOD_NODES = {"declaration", "field_declaration", "function_definition"}
_TYPE_NODES = {"class_specifier", "struct_specifier", "union_specifier", "enum_specifier"}
_TYPE_SYMBOLS = {
    "class_specifier": SymbolType.CLASS,
    "struct_specifier": SymbolType.STRUCT,
    "union_specifier": SymbolType.UNION,
    "enum_specifier": SymbolType.ENUM,
}
_ACCESS_DEFAULT = {
    "class_specifier": Visibility.PRIVATE,
    "struct_specifier": Visibility.PUBLIC,
    "union_specifier": Visibility.PUBLIC,
}


class CFamilyParser(BaseParser):
    """Structural extractor for C and C++ source files."""

    def __init__(self, language: Language) -> None:
        if language not in _SUFFIXES:
            raise ValueError(f"CFamilyParser does not support {language}")
        self._language = language

    def get_language(self) -> Language:
        return self._language

    def get_parser_name(self) -> str:
        return _PARSER_NAMES[self._language]

    def get_parser_version(self) -> str:
        try:
            return version(_PARSER_NAMES[self._language])
        except Exception:
            return "unknown"

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in _SUFFIXES[self._language]

    def parse(self, file_path: Path, relative_path: str) -> ParseResult:
        parser_version = self.get_parser_version()
        try:
            content = file_path.read_bytes()
            tree = load_parser(self._language).parse(content)
        except (OSError, ValueError) as error:
            return self._failure(relative_path, parser_version, f"read/parse failed: {error}")

        issues: list[ParseIssue] = []
        error_nodes = count_error_nodes(tree.root_node)
        if error_nodes:
            issues.append(
                ParseIssue(
                    file_path=relative_path,
                    parser=self.get_parser_name(),
                    reason=f"{error_nodes} syntax error node(s) in parse tree",
                    parser_version=parser_version,
                    timestamp=time.time(),
                )
            )

        symbols: list[SymbolInfo] = []
        namespaces: list[NamespaceInput] = []
        references: list[SymbolReference] = []
        self._walk(
            tree.root_node,
            relative_path,
            prefix="",
            parent=None,
            namespace=None,
            access=Visibility.UNKNOWN,
            template_prefix="",
            symbols=symbols,
            namespaces=namespaces,
            references=references,
        )
        return ParseResult(
            file_path=relative_path,
            language=self._language,
            parser_name=self.get_parser_name(),
            parser_version=parser_version,
            ok=True,
            symbols=symbols,
            namespaces=namespaces,
            references=references,
            issues=issues,
        )

    def _failure(self, relative_path: str, parser_version: str, reason: str) -> ParseResult:
        return ParseResult(
            file_path=relative_path,
            language=self._language,
            parser_name=self.get_parser_name(),
            parser_version=parser_version,
            ok=False,
            issues=[
                ParseIssue(
                    file_path=relative_path,
                    parser=self.get_parser_name(),
                    reason=reason,
                    parser_version=parser_version,
                    timestamp=time.time(),
                )
            ],
        )

    def _walk(
        self,
        node: tree_sitter.Node,
        relative_path: str,
        *,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        access: Visibility,
        template_prefix: str,
        symbols: list[SymbolInfo],
        namespaces: list[NamespaceInput],
        references: list[SymbolReference],
    ) -> None:
        """Recursive extraction over a declaration scope."""
        scope = dict(
            relative_path=relative_path,
            prefix=prefix,
            parent=parent,
            namespace=namespace,
            access=access,
            template_prefix=template_prefix,
            symbols=symbols,
            namespaces=namespaces,
            references=references,
        )
        if node.type == "template_declaration":
            head = _template_head(node)
            for child in node.named_children:
                self._walk(child, template_prefix=(template_prefix + " " + head).strip(),
                           **{k: v for k, v in scope.items() if k != "template_prefix"})
            return

        if node.type == "namespace_definition":
            self._handle_namespace(node, **scope)
            return

        if node.type in _TYPE_NODES:
            self._handle_type(node, **scope)
            return

        if node.type == "type_definition":
            self._handle_typedef(node, **scope)
            for child in node.named_children:
                if child.type in _TYPE_NODES:
                    self._walk(child, **scope)
            return

        if node.type in _METHOD_NODES and _function_declarator(node) is not None:
            self._handle_function(node, _function_declarator(node), **scope)
            return

        for child in node.named_children:
            self._walk(child, **scope)

    def _handle_namespace(
        self,
        node: tree_sitter.Node,
        *,
        relative_path: str,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        access: Visibility,
        template_prefix: str,
        symbols: list[SymbolInfo],
        namespaces: list[NamespaceInput],
        references: list[SymbolReference],
    ) -> None:
        name_node = field(node, "name")
        name = node_text(name_node) if name_node is not None else "<anonymous>"
        full_name = f"{prefix}{name}" if prefix else name
        # `namespace a::b` (and `a::b::c`) declares every component not
        # already declared by an enclosing namespace scope.
        parts = full_name.split(_SEPARATOR)
        prefix_depth = len(prefix.rstrip(_SEPARATOR).split(_SEPARATOR)) if prefix else 0
        for index in range(prefix_depth, len(parts)):
            namespaces.append(
                NamespaceInput(
                    namespace_name=_SEPARATOR.join(parts[: index + 1]),
                    parent_name=_SEPARATOR.join(parts[:index]) or None,
                )
            )
        body = field(node, "body")
        if body is not None:
            for child in body.named_children:
                self._walk(
                    child,
                    relative_path,
                    prefix=full_name + _SEPARATOR,
                    parent=None,
                    namespace=full_name,
                    access=Visibility.UNKNOWN,
                    template_prefix="",
                    symbols=symbols,
                    namespaces=namespaces,
                    references=references,
                )

    def _handle_type(
        self,
        node: tree_sitter.Node,
        *,
        relative_path: str,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        access: Visibility,
        template_prefix: str,
        symbols: list[SymbolInfo],
        namespaces: list[NamespaceInput],
        references: list[SymbolReference],
    ) -> None:
        name_node = field(node, "name")
        body = field(node, "body")
        member_access = _ACCESS_DEFAULT.get(node.type, Visibility.UNKNOWN)
        if name_node is None:
            # Anonymous type: record no symbol, but nested named members of
            # the enclosing scope still need extraction.
            if body is not None:
                self._walk_members(
                    body, relative_path,
                    prefix=prefix, parent=parent, namespace=namespace,
                    default_access=member_access, symbols=symbols,
                    namespaces=namespaces, references=references,
                )
            return

        name = node_text(name_node)
        fqn = f"{prefix}{name}" if prefix else name
        symbol_type = _TYPE_SYMBOLS[node.type]
        signature = (template_prefix + " " + declaration_signature(node)).strip() or None
        symbols.append(
            SymbolInfo(
                name=name,
                fully_qualified_name=fqn,
                symbol_type=symbol_type,
                language=self._language,
                file_path=relative_path,
                parent=parent,
                namespace=namespace,
                visibility=access,
                signature=signature,
                start_line=node.start_point.row + 1,
                end_line=node.end_point.row + 1,
                fingerprint=symbol_fingerprint(symbol_type, fqn, signature),
            )
        )

        # base_class_clause is a named child, not a named field, in the C++
        # grammar.
        base_clause = next(
            (child for child in node.named_children if child.type == "base_class_clause"),
            None,
        )
        if base_clause is not None:
            for base in base_clause.named_children:
                if base.type == "access_specifier":
                    continue
                references.append(
                    SymbolReference(
                        source_fqn=fqn,
                        target_name=node_text(base).strip(),
                        relationship_type=RelationshipType.INHERITS,
                    )
                )

        if body is not None:
            self._walk_members(
                body, relative_path,
                prefix=fqn + _SEPARATOR, parent=fqn, namespace=namespace,
                default_access=member_access, symbols=symbols,
                namespaces=namespaces, references=references,
            )

    def _walk_members(
        self,
        body: tree_sitter.Node,
        relative_path: str,
        *,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        default_access: Visibility,
        symbols: list[SymbolInfo],
        namespaces: list[NamespaceInput],
        references: list[SymbolReference],
    ) -> None:
        """Walk a type body (or anonymous type body), tracking access."""
        access = default_access
        for child in body.named_children:
            if child.type == "access_specifier":
                access = Visibility(node_text(child).strip().rstrip(":"))
                continue
            if child.type in _TYPE_NODES:
                self._handle_type(
                    child,
                    relative_path=relative_path,
                    prefix=prefix,
                    parent=parent,
                    namespace=namespace,
                    access=access,
                    template_prefix="",
                    symbols=symbols,
                    namespaces=namespaces,
                    references=references,
                )
            elif child.type == "template_declaration":
                head = _template_head(child)
                for inner in child.named_children:
                    if inner.type in _TYPE_NODES:
                        self._handle_type(
                            inner,
                            relative_path=relative_path,
                            prefix=prefix,
                            parent=parent,
                            namespace=namespace,
                            access=access,
                            template_prefix=head,
                            symbols=symbols,
                            namespaces=namespaces,
                            references=references,
                        )
                    elif inner.type in _METHOD_NODES and _function_declarator(inner) is not None:
                        self._handle_function(
                            inner, _function_declarator(inner),
                            relative_path=relative_path,
                            prefix=prefix, parent=parent, namespace=namespace,
                            access=access, template_prefix=head, symbols=symbols,
                            namespaces=namespaces, references=references,
                        )
            elif child.type in _METHOD_NODES and _function_declarator(child) is not None:
                self._handle_function(
                    child, _function_declarator(child),
                    relative_path=relative_path,
                    prefix=prefix, parent=parent, namespace=namespace,
                    access=access, template_prefix="", symbols=symbols,
                    namespaces=namespaces, references=references,
                )

    def _handle_function(
        self,
        node: tree_sitter.Node,
        declarator: tree_sitter.Node | None,
        *,
        relative_path: str,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        access: Visibility,
        template_prefix: str,
        symbols: list[SymbolInfo],
        namespaces: list[NamespaceInput],
        references: list[SymbolReference],
    ) -> None:
        if declarator is None:
            return
        name_node = field(declarator, "declarator")
        if name_node is None:
            return
        symbol_type = SymbolType.FUNCTION
        if name_node.type == "destructor_name":
            name = node_text(name_node).strip()
            symbol_type = SymbolType.DESTRUCTOR
        else:
            name = node_text(name_node).strip()
            if not name:
                return
            if parent is not None:
                symbol_type = (
                    SymbolType.CONSTRUCTOR
                    if name == parent.split(_SEPARATOR)[-1]
                    else SymbolType.METHOD
                )
        fqn = f"{prefix}{name}" if prefix else name
        signature = (template_prefix + " " + declaration_signature(node)).strip() or None
        symbols.append(
            SymbolInfo(
                name=name,
                fully_qualified_name=fqn,
                symbol_type=symbol_type,
                language=self._language,
                file_path=relative_path,
                parent=parent,
                namespace=namespace,
                visibility=access,
                signature=signature,
                start_line=node.start_point.row + 1,
                end_line=node.end_point.row + 1,
                fingerprint=symbol_fingerprint(symbol_type, fqn, signature),
            )
        )

    def _handle_typedef(
        self,
        node: tree_sitter.Node,
        *,
        relative_path: str,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        access: Visibility,
        template_prefix: str,
        symbols: list[SymbolInfo],
        namespaces: list[NamespaceInput],
        references: list[SymbolReference],
    ) -> None:
        declarator = field(node, "declarator")
        if declarator is None:
            return
        name = _declarator_name(declarator)
        if name is None:
            return
        fqn = f"{prefix}{name}" if prefix else name
        signature = (template_prefix + " " + declaration_signature(node)).strip() or None
        symbols.append(
            SymbolInfo(
                name=name,
                fully_qualified_name=fqn,
                symbol_type=SymbolType.TYPEDEF,
                language=self._language,
                file_path=relative_path,
                parent=parent,
                namespace=namespace,
                visibility=access,
                signature=signature,
                start_line=node.start_point.row + 1,
                end_line=node.end_point.row + 1,
                fingerprint=symbol_fingerprint(SymbolType.TYPEDEF, fqn, signature),
            )
        )


def _template_head(node: tree_sitter.Node) -> str:
    for child in node.named_children:
        if child.type == "template_parameter_list":
            return f"template<{node_text(child).strip('<>')}>"
    return "template<...>"


def _function_declarator(node: tree_sitter.Node) -> tree_sitter.Node | None:
    """Find the function_declarator in a declaration's declarator chain."""
    current = field(node, "declarator")
    while current is not None:
        if current.type == "function_declarator":
            return current
        current = field(current, "declarator")
    return None


def _declarator_name(node: tree_sitter.Node) -> str | None:
    """Extract the declared name from a declarator chain."""
    current: tree_sitter.Node | None = node
    while current is not None:
        if current.type in ("identifier", "field_identifier", "type_identifier",
                            "destructor_name", "qualified_identifier"):
            return node_text(current)
        current = field(current, "declarator")
    return None

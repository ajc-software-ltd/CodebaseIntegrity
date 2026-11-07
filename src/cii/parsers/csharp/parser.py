"""C# structural extraction (tree-sitter).

Extraction categories (PLAN.md §8.2, verified against the grammar):
- namespace_declaration → namespace declarations (dotted names expanded)
- class/struct/interface/record/enum declarations → types
- method/constructor/destructor/property/event/delegate declarations → members
- base_list → inherits/implements relationships (parser evidence)
- modifier nodes → visibility (C# defaults applied when absent)

Not extracted (outside the v0.1 spec): fields. Interface implementations are
recorded as `implements` from the base list with reduced confidence: a purely
syntactic parser cannot prove which base names are interfaces.
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

_SEPARATOR = "."
_SUFFIXES = {".cs"}
_PARSER_NAME = "tree-sitter-c-sharp"

_TYPE_NODES = {
    "class_declaration": SymbolType.CLASS,
    "struct_declaration": SymbolType.STRUCT,
    "interface_declaration": SymbolType.INTERFACE,
    "record_declaration": SymbolType.RECORD,
    "record_class_declaration": SymbolType.RECORD,
    "record_struct_declaration": SymbolType.RECORD,
    "enum_declaration": SymbolType.ENUM,
}
_MEMBER_NODES = {
    "method_declaration": SymbolType.METHOD,
    "constructor_declaration": SymbolType.CONSTRUCTOR,
    "destructor_declaration": SymbolType.DESTRUCTOR,
    "property_declaration": SymbolType.PROPERTY,
    "event_field_declaration": SymbolType.EVENT,
    "delegate_declaration": SymbolType.DELEGATE,
}
_VISIBILITY_WORDS = {
    "public": Visibility.PUBLIC,
    "private": Visibility.PRIVATE,
    "protected": Visibility.PROTECTED,
    "internal": Visibility.INTERNAL,
}


class CSharpParser(BaseParser):
    """Structural extractor for C# source files."""

    def get_language(self) -> Language:
        return Language.CSHARP

    def get_parser_name(self) -> str:
        return _PARSER_NAME

    def get_parser_version(self) -> str:
        try:
            return version(_PARSER_NAME)
        except Exception:
            return "unknown"

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in _SUFFIXES

    def parse(self, file_path: Path, relative_path: str) -> ParseResult:
        parser_version = self.get_parser_version()
        try:
            content = file_path.read_bytes()
            tree = load_parser(Language.CSHARP).parse(content)
        except (OSError, ValueError) as error:
            return ParseResult(
                file_path=relative_path,
                language=Language.CSHARP,
                parser_name=_PARSER_NAME,
                parser_version=parser_version,
                ok=False,
                issues=[ParseIssue(
                    file_path=relative_path, parser=_PARSER_NAME,
                    reason=f"read/parse failed: {error}",
                    parser_version=parser_version, timestamp=time.time(),
                )],
            )

        issues: list[ParseIssue] = []
        error_nodes = count_error_nodes(tree.root_node)
        if error_nodes:
            issues.append(ParseIssue(
                file_path=relative_path, parser=_PARSER_NAME,
                reason=f"{error_nodes} syntax error node(s) in parse tree",
                parser_version=parser_version, timestamp=time.time(),
            ))

        symbols: list[SymbolInfo] = []
        namespaces: list[NamespaceInput] = []
        references: list[SymbolReference] = []
        self._walk(tree.root_node, relative_path, prefix="", parent=None,
                   namespace=None, symbols=symbols, namespaces=namespaces,
                   references=references)
        return ParseResult(
            file_path=relative_path,
            language=Language.CSHARP,
            parser_name=_PARSER_NAME,
            parser_version=parser_version,
            ok=True,
            symbols=symbols,
            namespaces=namespaces,
            references=references,
            issues=issues,
        )

    def _walk(
        self,
        node: tree_sitter.Node,
        relative_path: str,
        *,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        symbols: list[SymbolInfo],
        namespaces: list[NamespaceInput],
        references: list[SymbolReference],
    ) -> None:
        if node.type in ("namespace_declaration", "file_scoped_namespace_declaration"):
            name_node = field(node, "name")
            full_name = node_text(name_node) if name_node is not None else "<anonymous>"
            full_name = full_name.strip()
            if prefix:
                full_name = f"{prefix}{_SEPARATOR}{full_name}"
            parts = full_name.split(_SEPARATOR)
            prefix_depth = (
                len(prefix.rstrip(_SEPARATOR).split(_SEPARATOR)) if prefix else 0
            )
            for index in range(prefix_depth, len(parts)):
                namespaces.append(NamespaceInput(
                    namespace_name=_SEPARATOR.join(parts[: index + 1]),
                    parent_name=_SEPARATOR.join(parts[:index]) or None,
                ))
            body = field(node, "body")
            if body is not None:
                for child in body.named_children:
                    self._walk(child, relative_path, prefix=full_name, parent=None,
                               namespace=full_name, symbols=symbols,
                               namespaces=namespaces, references=references)
            return

        if node.type in _TYPE_NODES:
            self._handle_type(node, relative_path, prefix=prefix, parent=parent,
                              namespace=namespace, symbols=symbols,
                              namespaces=namespaces, references=references)
            return

        for child in node.named_children:
            self._walk(child, relative_path, prefix=prefix, parent=parent,
                       namespace=namespace, symbols=symbols,
                       namespaces=namespaces, references=references)

    def _handle_type(
        self,
        node: tree_sitter.Node,
        relative_path: str,
        *,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        symbols: list[SymbolInfo],
        namespaces: list[NamespaceInput],
        references: list[SymbolReference],
    ) -> None:
        name_node = field(node, "name")
        if name_node is None:
            return
        name = node_text(name_node)
        fqn = f"{prefix}{_SEPARATOR}{name}" if prefix else name
        symbol_type = _TYPE_NODES[node.type]
        visibility = _visibility_of(node, in_type=parent is not None)
        signature = declaration_signature(node) or None
        symbols.append(SymbolInfo(
            name=name,
            fully_qualified_name=fqn,
            symbol_type=symbol_type,
            language=Language.CSHARP,
            file_path=relative_path,
            parent=parent,
            namespace=namespace,
            visibility=visibility,
            signature=signature,
            start_line=node.start_point.row + 1,
            end_line=node.end_point.row + 1,
            fingerprint=symbol_fingerprint(symbol_type, fqn, signature),
        ))

        # base_list is a named child, not a named field, in the C# grammar.
        base_list = next(
            (child for child in node.named_children if child.type == "base_list"), None
        )
        if base_list is not None:
            base_names = [node_text(child).strip() for child in base_list.named_children]
            base_names = [base_name for base_name in base_names if base_name]
            for index, base_name in enumerate(base_names):
                if symbol_type is SymbolType.INTERFACE:
                    relationship = RelationshipType.INHERITS
                    confidence = 1.0
                elif index == 0:
                    relationship = RelationshipType.INHERITS
                    confidence = 0.8
                else:
                    relationship = RelationshipType.IMPLEMENTS
                    confidence = 0.8
                references.append(SymbolReference(
                    source_fqn=fqn,
                    target_name=base_name,
                    relationship_type=relationship,
                    confidence=confidence,
                ))

        body = field(node, "body")
        if body is None:
            return
        for child in body.named_children:
            if child.type in _TYPE_NODES:
                self._handle_type(child, relative_path, prefix=fqn, parent=fqn,
                                  namespace=namespace, symbols=symbols,
                                  namespaces=namespaces, references=references)
            elif child.type in _MEMBER_NODES:
                self._handle_member(child, relative_path, prefix=fqn, parent=fqn,
                                    namespace=namespace, symbols=symbols)

    def _handle_member(
        self,
        node: tree_sitter.Node,
        relative_path: str,
        *,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        symbols: list[SymbolInfo],
    ) -> None:
        if node.type == "event_field_declaration":
            # events declare names through variable_declarator children
            for child in node.named_children:
                for declarator in child.named_children:
                    if declarator.type == "variable_declarator":
                        self._append_member(declarator, SymbolType.EVENT, name=None,
                                            node=node, relative_path=relative_path,
                                            prefix=prefix, parent=parent,
                                            namespace=namespace, symbols=symbols)
            return
        name_node = field(node, "name")
        if name_node is None:
            return
        name = node_text(name_node)
        symbol_type = _MEMBER_NODES[node.type]
        self._append_member(node, symbol_type, name=name, node=node,
                            relative_path=relative_path, prefix=prefix,
                            parent=parent, namespace=namespace, symbols=symbols)

    def _append_member(
        self,
        name_source: tree_sitter.Node,
        symbol_type: SymbolType,
        *,
        name: str | None,
        node: tree_sitter.Node,
        relative_path: str,
        prefix: str,
        parent: str | None,
        namespace: str | None,
        symbols: list[SymbolInfo],
    ) -> None:
        if name is None:
            name_node = field(name_source, "name")
            if name_node is None:
                return
            name = node_text(name_node)
        fqn = f"{prefix}{_SEPARATOR}{name}" if prefix else name
        signature = declaration_signature(node) or None
        symbols.append(SymbolInfo(
            name=name,
            fully_qualified_name=fqn,
            symbol_type=symbol_type,
            language=Language.CSHARP,
            file_path=relative_path,
            parent=parent,
            namespace=namespace,
            visibility=_visibility_of(node, in_type=True),
            signature=signature,
            start_line=node.start_point.row + 1,
            end_line=node.end_point.row + 1,
            fingerprint=symbol_fingerprint(symbol_type, fqn, signature),
        ))


def _visibility_of(node: tree_sitter.Node, *, in_type: bool) -> Visibility:
    """Read visibility from modifier nodes; apply C# defaults when absent."""
    for child in node.named_children:
        if child.type == "modifier":
            word = node_text(child).strip()
            if word in _VISIBILITY_WORDS:
                return _VISIBILITY_WORDS[word]
    if in_type:
        return Visibility.PRIVATE  # C# member default
    return Visibility.INTERNAL  # C# top-level type default

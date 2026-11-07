"""Table-driven tree-sitter extraction for the extended language set.

Languages added after v1.0 (JavaScript, TypeScript, Rust, Java, Go, Lua,
CMake — PLAN.md §8.3) share one structural shape: namespace-like scoping,
type declarations, and callable declarations. Rather than one module per
language, each language is described by an :class:`ExtractSpec` and walked by
:class:`SpecParser`. Language quirks (Go receivers, Rust impl blocks, Lua
dotted method names, CMake function commands) plug in as small hooks.

GLSL and HLSL are not handled here: their grammars produce C-shaped trees and
reuse ``CFamilyParser`` directly.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import version as package_version
from pathlib import Path

import tree_sitter

from cii.core.enums import Language, RelationshipType, SymbolType, Visibility
from cii.core.models import NamespaceInput, SymbolInfo, symbol_fingerprint
from cii.parsers.base import BaseParser, ParseIssue, ParseResult, SymbolReference
from cii.parsers.treesitter.language_registry import load_parser
from cii.parsers.treesitter.parser import (
    count_error_nodes,
    declaration_signature,
    field as node_field,
    node_text,
)

# A name hook resolves a callable node into (name, parent_name, symbol_type):
# parent_name is a local name resolved against the current scope prefix.
NameHook = Callable[[tree_sitter.Node], "tuple[str, str | None, SymbolType] | None"]
# A heritage hook extracts relationship evidence from a type declaration node.
HeritageHook = Callable[[tree_sitter.Node, str], list[SymbolReference]]


@dataclass(frozen=True)
class ExtractSpec:
    """Declarative extraction rules for one language."""

    language: Language
    separator: str
    parser_name: str
    grammar_package: str
    namespace_nodes: dict[str, str] = field(default_factory=dict)  # node -> name field
    expand_namespace_dots: bool = False
    type_nodes: dict[str, SymbolType] = field(default_factory=dict)
    function_nodes: dict[str, SymbolType] = field(default_factory=dict)
    constructor_names: frozenset[str] = frozenset()
    transparent_nodes: frozenset[str] = frozenset()
    impl_nodes: frozenset[str] = frozenset()
    type_kind_hook: Callable[[tree_sitter.Node], SymbolType] | None = None
    name_hook: NameHook | None = None
    heritage_hook: HeritageHook | None = None
    visibility: Callable[[tree_sitter.Node, bool], Visibility] | None = None
    default_type_visibility: Visibility = Visibility.UNKNOWN
    default_member_visibility: Visibility = Visibility.UNKNOWN


class SpecParser(BaseParser):
    """Generic extractor driven by an :class:`ExtractSpec`."""

    def __init__(self, spec: ExtractSpec) -> None:
        self._spec = spec

    def get_language(self) -> Language:
        return self._spec.language

    def get_parser_name(self) -> str:
        return self._spec.parser_name

    def get_parser_version(self) -> str:
        try:
            return package_version(self._spec.grammar_package)
        except Exception:
            return "unknown"

    def supports(self, file_path: Path) -> bool:
        from cii.core.configuration import DEFAULT_EXTENSIONS

        wanted = {
            ext for ext, lang in DEFAULT_EXTENSIONS.items() if lang == self._spec.language.value
        }
        return file_path.suffix.lower() in wanted

    def parse(self, file_path: Path, relative_path: str) -> ParseResult:
        parser_version = self.get_parser_version()
        try:
            content = file_path.read_bytes()
            tree = load_parser(self._spec.language).parse(content)
        except Exception as error:  # grammar/IO failures become reported issues
            return ParseResult(
                file_path=relative_path,
                language=self._spec.language,
                parser_name=self._spec.parser_name,
                parser_version=parser_version,
                ok=False,
                issues=[ParseIssue(
                    file_path=relative_path, parser=self._spec.parser_name,
                    reason=f"read/parse failed: {error}",
                    parser_version=parser_version, timestamp=time.time(),
                )],
            )

        issues: list[ParseIssue] = []
        error_nodes = count_error_nodes(tree.root_node)
        if error_nodes:
            issues.append(ParseIssue(
                file_path=relative_path, parser=self._spec.parser_name,
                reason=f"{error_nodes} syntax error node(s) in parse tree",
                parser_version=parser_version, timestamp=time.time(),
            ))

        symbols: list[SymbolInfo] = []
        namespaces: list[NamespaceInput] = []
        references: list[SymbolReference] = []
        self._walk(tree.root_node, relative_path, prefix="", parent=None,
                   namespace=None, in_type=False,
                   symbols=symbols, namespaces=namespaces, references=references)
        return ParseResult(
            file_path=relative_path,
            language=self._spec.language,
            parser_name=self._spec.parser_name,
            parser_version=parser_version,
            ok=True,
            symbols=symbols,
            namespaces=namespaces,
            references=references,
            issues=issues,
        )

    # ---- walking -------------------------------------------------------

    def _walk(self, node, relative_path, *, prefix, parent, namespace, in_type,
              symbols, namespaces, references) -> None:
        spec = self._spec
        if node.type in spec.transparent_nodes:
            for child in node.named_children:
                self._walk(child, relative_path, prefix=prefix, parent=parent,
                           namespace=namespace, in_type=in_type,
                           symbols=symbols, namespaces=namespaces, references=references)
            return

        if node.type in spec.namespace_nodes:
            self._handle_namespace(node, relative_path, prefix=prefix,
                                   symbols=symbols, namespaces=namespaces,
                                   references=references)
            return

        if node.type in spec.impl_nodes:
            self._handle_impl(node, relative_path, prefix=prefix, namespace=namespace,
                              symbols=symbols, namespaces=namespaces, references=references)
            return

        if node.type in spec.type_nodes:
            self._handle_type(node, relative_path, prefix=prefix, parent=parent,
                              namespace=namespace, in_type=in_type,
                              symbols=symbols, namespaces=namespaces,
                              references=references)
            return

        if node.type in spec.function_nodes:
            self._handle_function(node, relative_path, prefix=prefix, parent=parent,
                                  namespace=namespace, in_type=in_type, symbols=symbols,
                                  namespaces=namespaces, references=references)
            return

        for child in node.named_children:
            self._walk(child, relative_path, prefix=prefix, parent=parent,
                       namespace=namespace, in_type=in_type,
                       symbols=symbols, namespaces=namespaces, references=references)

    def _handle_namespace(self, node, relative_path, *, prefix, symbols,
                          namespaces, references) -> None:
        name_node = node_field(node, self._spec.namespace_nodes[node.type])
        name = node_text(name_node).strip() if name_node is not None else "<anonymous>"
        full = f"{prefix}{self._spec.separator}{name}" if prefix else name
        if self._spec.expand_namespace_dots:
            parts = full.replace(self._spec.separator, ".").split(".")
            joiner = self._spec.separator
            prefix_depth = (
                len(prefix.replace(joiner, ".").rstrip(".").split(".")) if prefix else 0
            )
            for index in range(prefix_depth, len(parts)):
                namespaces.append(NamespaceInput(
                    namespace_name=joiner.join(parts[: index + 1]),
                    parent_name=joiner.join(parts[:index]) or None,
                ))
        else:
            namespaces.append(NamespaceInput(
                namespace_name=full.replace(".", self._spec.separator),
                parent_name=prefix or None,
            ))
        body = node_field(node, "body")
        if body is not None:
            for child in body.named_children:
                self._walk(child, relative_path,
                           prefix=full + self._spec.separator, parent=None,
                           namespace=full, in_type=False,
                           symbols=symbols, namespaces=namespaces, references=references)

    def _handle_type(self, node, relative_path, *, prefix, parent, namespace,
                     in_type, symbols, namespaces, references) -> None:
        spec = self._spec
        name_node = node_field(node, "name")
        if name_node is None:
            return
        name = node_text(name_node).strip()
        fqn = f"{prefix}{spec.separator}{name}" if prefix else name
        symbol_type = (
            spec.type_kind_hook(node) if spec.type_kind_hook is not None
            else spec.type_nodes[node.type]
        )
        visibility = self._visibility(node, in_type)
        signature = declaration_signature(node) or None
        symbols.append(SymbolInfo(
            name=name, fully_qualified_name=fqn, symbol_type=symbol_type,
            language=spec.language, file_path=relative_path, parent=parent,
            namespace=namespace, visibility=visibility, signature=signature,
            start_line=node.start_point.row + 1, end_line=node.end_point.row + 1,
            fingerprint=symbol_fingerprint(symbol_type, fqn, signature),
        ))
        if spec.heritage_hook is not None:
            references.extend(spec.heritage_hook(node, fqn))

        body = node_field(node, "body")
        if body is None:
            return
        for child in body.named_children:
            self._walk(child, relative_path,
                       prefix=fqn + spec.separator, parent=fqn,
                       namespace=namespace, in_type=True,
                       symbols=symbols, namespaces=namespaces, references=references)

    def _handle_impl(self, node, relative_path, *, prefix, namespace,
                     symbols, namespaces, references) -> None:
        """Rust-style `impl Trait for Type` blocks: functions belong to Type."""
        spec = self._spec
        type_node = node_field(node, "type")
        if type_node is None:
            return
        self_name = node_text(type_node).strip().split(spec.separator)[-1]
        fqn = f"{prefix}{spec.separator}{self_name}" if prefix else self_name
        trait_node = node_field(node, "trait")
        if trait_node is not None:
            references.append(SymbolReference(
                source_fqn=fqn, target_name=node_text(trait_node).strip(),
                relationship_type=RelationshipType.IMPLEMENTS,
            ))
        body = node_field(node, "body")
        if body is not None:
            for child in body.named_children:
                self._walk(child, relative_path,
                           prefix=fqn + spec.separator, parent=fqn,
                           namespace=namespace, in_type=True,
                           symbols=symbols, namespaces=namespaces, references=references)

    def _handle_function(self, node, relative_path, *, prefix, parent, namespace,
                         in_type, symbols, namespaces, references) -> None:
        spec = self._spec
        name, parent_override, symbol_type = spec.name_hook(node) if spec.name_hook else (None, None, None)
        if name is None:
            name_node = node_field(node, "name")
            if name_node is None:
                return
            name = node_text(name_node).strip()
            symbol_type = spec.function_nodes[node.type]
        assert symbol_type is not None

        resolved_parent = parent
        if parent_override:
            resolved_parent = (
                f"{prefix}{spec.separator}{parent_override}"
                if prefix and spec.separator not in parent_override
                else parent_override
            )
            fqn = f"{resolved_parent}{spec.separator}{name}"
        else:
            fqn = f"{prefix}{spec.separator}{name}" if prefix else name

        if resolved_parent is not None:
            if name == resolved_parent.split(spec.separator)[-1]:
                symbol_type = SymbolType.CONSTRUCTOR
            elif name in spec.constructor_names:
                symbol_type = SymbolType.CONSTRUCTOR

        signature = declaration_signature(node) or None
        symbols.append(SymbolInfo(
            name=name, fully_qualified_name=fqn, symbol_type=symbol_type,
            language=spec.language, file_path=relative_path, parent=resolved_parent,
            namespace=namespace, visibility=self._visibility(node, in_type),
            signature=signature,
            start_line=node.start_point.row + 1, end_line=node.end_point.row + 1,
            fingerprint=symbol_fingerprint(symbol_type, fqn, signature),
        ))
        # nested declarations (e.g. Lua/JS inner functions) live in the body
        for child in node.named_children:
            if child.type in ("formal_parameters", "parameters", "parameter_list",
                              "identifier", "field_identifier", "property_identifier",
                              "type", "receiver", "return_type", "semantics"):
                continue
            self._walk(child, relative_path,
                       prefix=fqn + spec.separator, parent=fqn,
                       namespace=namespace, in_type=in_type,
                       symbols=symbols, namespaces=namespaces, references=references)

    def _visibility(self, node, in_type: bool) -> Visibility:
        spec = self._spec
        if spec.visibility is not None:
            return spec.visibility(node, in_type)
        return spec.default_member_visibility if in_type else spec.default_type_visibility

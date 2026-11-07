"""Language extraction specs for the extended language set (PLAN.md §8.3).

Each spec is the declarative extraction contract for one language; quirks are
small hooks backed by verified grammar node shapes. Heritage hooks record
inheritance evidence where the grammar makes it provable; languages without an
inheritance concept (Go, Lua, CMake) record none rather than guessing.
"""

import tree_sitter

from cii.core.enums import Language, RelationshipType, SymbolType, Visibility
from cii.core.models import symbol_fingerprint  # noqa: F401  (re-export convenience)
from cii.parsers.base import SymbolReference
from cii.parsers.treesitter.generic import ExtractSpec
from cii.parsers.treesitter.parser import field as node_field
from cii.parsers.treesitter.parser import node_text


def _split_types(text: str) -> list[str]:
    names = []
    for part in text.replace("extends", " ").replace("implements", " ").split(","):
        name = part.strip().split("<")[0].strip()
        if name and name.isidentifier() or (name and "." in name):
            names.append(name)
    return names


def _js_heritage(node: tree_sitter.Node, fqn: str) -> list[SymbolReference]:
    refs: list[SymbolReference] = []
    for child in node.named_children:
        if child.type != "class_heritage":
            continue
        text = node_text(child)
        extends_part, _, implements_part = text.partition("implements")
        for name in _split_types(extends_part):
            refs.append(SymbolReference(
                source_fqn=fqn, target_name=name,
                relationship_type=RelationshipType.INHERITS))
        for name in _split_types(implements_part):
            refs.append(SymbolReference(
                source_fqn=fqn, target_name=name,
                relationship_type=RelationshipType.IMPLEMENTS))
    return refs


def _ts_heritage(node: tree_sitter.Node, fqn: str) -> list[SymbolReference]:
    refs: list[SymbolReference] = []
    for child in node.named_children:
        if child.type in ("class_heritage", "extends_type_clause"):
            text = node_text(child)
            extends_part, _, implements_part = text.partition("implements")
            relation = RelationshipType.INHERITS
            for name in _split_types(extends_part):
                refs.append(SymbolReference(
                    source_fqn=fqn, target_name=name, relationship_type=relation))
            for name in _split_types(implements_part):
                refs.append(SymbolReference(
                    source_fqn=fqn, target_name=name,
                    relationship_type=RelationshipType.IMPLEMENTS))
    return refs


def _java_heritage(node: tree_sitter.Node, fqn: str) -> list[SymbolReference]:
    refs: list[SymbolReference] = []
    for child in node.named_children:
        if child.type == "superclass":
            for name in _split_types(node_text(child)):
                refs.append(SymbolReference(
                    source_fqn=fqn, target_name=name,
                    relationship_type=RelationshipType.INHERITS))
        elif child.type == "super_interfaces":
            for name in _split_types(node_text(child)):
                refs.append(SymbolReference(
                    source_fqn=fqn, target_name=name,
                    relationship_type=RelationshipType.IMPLEMENTS))
    return refs


def _java_visibility(node: tree_sitter.Node, in_type: bool) -> Visibility:
    for child in node.named_children:
        if child.type == "modifiers":
            words = node_text(child).split()
            for word in ("public", "protected", "private", "internal"):
                if word in words:
                    return Visibility(word)
    return Visibility.INTERNAL  # Java default: package-private


def _rust_visibility(node: tree_sitter.Node, in_type: bool) -> Visibility:
    for child in node.named_children:
        if child.type == "visibility_modifier":
            return Visibility.PUBLIC
    return Visibility.PRIVATE  # Rust default


def _go_visibility(node: tree_sitter.Node, in_type: bool) -> Visibility:
    name_node = node_field(node, "name")
    name = node_text(name_node) if name_node is not None else ""
    # Go's export rule: an upper-case first letter means exported.
    return Visibility.PUBLIC if name[:1].isupper() else Visibility.PRIVATE


def _go_type_kind(node: tree_sitter.Node) -> SymbolType:
    kind = node_field(node, "type")
    if kind is not None:
        if kind.type == "struct_type":
            return SymbolType.STRUCT
        if kind.type == "interface_type":
            return SymbolType.INTERFACE
    return SymbolType.TYPEDEF  # e.g. `type MyInt int`


def _go_name(node: tree_sitter.Node):
    name_node = node_field(node, "name")
    name = node_text(name_node).strip() if name_node is not None else None
    if name is None:
        return None
    if node.type == "method_declaration":
        receiver = node_field(node, "receiver")
        owner = None
        if receiver is not None and receiver.named_children:
            parameter = receiver.named_children[0]
            type_node = node_field(parameter, "type")
            if type_node is not None:
                target = type_node
                if target.type == "pointer_type":
                    target = target.named_children[0] if target.named_children else target
                owner = node_text(target).strip().split(".")[-1]
        return name, owner, SymbolType.METHOD
    return name, None, SymbolType.FUNCTION


def _lua_name(node: tree_sitter.Node):
    name_node = node_field(node, "name")
    if name_node is None:
        return None
    text = node_text(name_node).strip()
    for sep in (":", "."):
        if sep in text:
            owner, _, tail = text.rpartition(sep)
            return tail.strip(), owner.strip(), SymbolType.METHOD
    return text, None, SymbolType.FUNCTION


def _cmake_name(node: tree_sitter.Node):
    for child in node.named_children:
        if child.type in ("function_command", "macro_command"):
            arguments = next(
                (c for c in child.named_children if c.type == "argument_list"), None
            )
            if arguments is not None and arguments.named_children:
                first = arguments.named_children[0]
                return node_text(first).strip(), None, SymbolType.FUNCTION
    return None


JS = ExtractSpec(
    language=Language.JAVASCRIPT,
    separator=".",
    parser_name="tree-sitter-javascript",
    grammar_package="tree-sitter-javascript",
    type_nodes={"class_declaration": SymbolType.CLASS},
    function_nodes={
        "function_declaration": SymbolType.FUNCTION,
        "generator_function_declaration": SymbolType.FUNCTION,
        "method_definition": SymbolType.METHOD,
    },
    constructor_names=frozenset({"constructor"}),
    heritage_hook=_js_heritage,
)

TS = ExtractSpec(
    language=Language.TYPESCRIPT,
    separator=".",
    parser_name="tree-sitter-typescript",
    grammar_package="tree-sitter-typescript",
    namespace_nodes={"internal_module": ("name", "nested_identifier")},
    expand_namespace_dots=True,
    type_nodes={
        "class_declaration": SymbolType.CLASS,
        "abstract_class_declaration": SymbolType.CLASS,
        "interface_declaration": SymbolType.INTERFACE,
        "enum_declaration": SymbolType.ENUM,
        "type_alias_declaration": SymbolType.TYPEDEF,
    },
    function_nodes={
        "function_declaration": SymbolType.FUNCTION,
        "generator_function_declaration": SymbolType.FUNCTION,
        "method_definition": SymbolType.METHOD,
        "method_signature": SymbolType.METHOD,
        "abstract_method_signature": SymbolType.METHOD,
        "property_signature": SymbolType.PROPERTY,
    },
    constructor_names=frozenset({"constructor"}),
    transparent_nodes=frozenset({"export_statement", "expression_statement"}),
    heritage_hook=_ts_heritage,
)

RUST = ExtractSpec(
    language=Language.RUST,
    separator="::",
    parser_name="tree-sitter-rust",
    grammar_package="tree-sitter-rust",
    namespace_nodes={"mod_item": ("name", "identifier")},
    type_nodes={
        "struct_item": SymbolType.STRUCT,
        "enum_item": SymbolType.ENUM,
        "trait_item": SymbolType.INTERFACE,
        "union_item": SymbolType.STRUCT,
    },
    function_nodes={
        "function_item": SymbolType.FUNCTION,
        "function_signature_item": SymbolType.FUNCTION,
    },
    impl_nodes=frozenset({"impl_item"}),
    visibility=_rust_visibility,
)

JAVA = ExtractSpec(
    language=Language.JAVA,
    separator=".",
    parser_name="tree-sitter-java",
    grammar_package="tree-sitter-java",
    namespace_nodes={"package_declaration": (None, "scoped_identifier")},
    expand_namespace_dots=True,
    type_nodes={
        "class_declaration": SymbolType.CLASS,
        "interface_declaration": SymbolType.INTERFACE,
        "enum_declaration": SymbolType.ENUM,
        "record_declaration": SymbolType.RECORD,
        "annotation_type_declaration": SymbolType.INTERFACE,
    },
    function_nodes={
        "method_declaration": SymbolType.METHOD,
        "constructor_declaration": SymbolType.CONSTRUCTOR,
        "compact_constructor_declaration": SymbolType.CONSTRUCTOR,
    },
    heritage_hook=_java_heritage,
    visibility=_java_visibility,
)

GO = ExtractSpec(
    language=Language.GO,
    separator=".",
    parser_name="tree-sitter-go",
    grammar_package="tree-sitter-go",
    namespace_nodes={"package_clause": (None, "package_identifier")},
    type_nodes={"type_spec": SymbolType.STRUCT},
    type_kind_hook=_go_type_kind,
    function_nodes={
        "function_declaration": SymbolType.FUNCTION,
        "method_declaration": SymbolType.METHOD,
    },
    name_hook=_go_name,
    visibility=_go_visibility,
)

LUA = ExtractSpec(
    language=Language.LUA,
    separator=".",
    parser_name="tree-sitter-lua",
    grammar_package="tree-sitter-lua",
    function_nodes={"function_declaration": SymbolType.FUNCTION},
    name_hook=_lua_name,
)

CMAKE = ExtractSpec(
    language=Language.CMAKE,
    separator=".",
    parser_name="tree-sitter-cmake",
    grammar_package="tree-sitter-cmake",
    function_nodes={
        "function_def": SymbolType.FUNCTION,
        "macro_def": SymbolType.FUNCTION,
    },
    name_hook=_cmake_name,
)

NEW_LANGUAGE_SPECS: list[ExtractSpec] = [JS, TS, RUST, JAVA, GO, LUA, CMAKE]

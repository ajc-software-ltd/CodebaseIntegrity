"""Shared tree-sitter extraction utilities.

Small, focused helpers used by the C/C++ and C# extractors: node text access,
signature extraction (declaration header without body), and error-node
detection. Extraction rules themselves live in each language's parser module.
"""

import tree_sitter

from cii.parsers.base import normalise_signature


def node_text(node: tree_sitter.Node) -> str:
    """Return a node's source text decoded as UTF-8."""
    return node.text.decode("utf-8", errors="replace") if node.text else ""


def field(node: tree_sitter.Node, name: str) -> tree_sitter.Node | None:
    """Return a named field of a node, or None."""
    return node.child_by_field_name(name)


def declaration_signature(node: tree_sitter.Node) -> str:
    """Return the declaration header of a node, excluding its body.

    For a definition, this is the text up to the body's start byte; for a
    declaration, the whole node text without the trailing semicolon.
    """
    body = node.child_by_field_name("body")
    text = node_text(node)
    if body is not None and body.start_byte > node.start_byte:
        text = node.text[: body.start_byte - node.start_byte].decode("utf-8", errors="replace")
    text = text.rstrip().rstrip(";").rstrip()
    return normalise_signature(text)


def count_error_nodes(root: tree_sitter.Node) -> int:
    """Count ERROR and missing nodes in a tree (parse-quality evidence)."""
    count = 0
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "ERROR" or node.is_missing:
            count += 1
        stack.extend(node.named_children)
    return count

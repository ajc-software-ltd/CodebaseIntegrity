"""Core enumerations shared across the CII subsystems.

Values are stable string identifiers: they are persisted in SQLite and exposed
through MCP responses, so they must not change without a schema migration.
"""

from enum import StrEnum


class Language(StrEnum):
    """Programming languages supported by the index (v0.1 scope).

    All PLAN.md sec 8.2-8.3 languages are implemented.
    """

    C = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    JAVA = "java"
    GO = "go"
    LUA = "lua"
    GLSL = "glsl"
    HLSL = "hlsl"
    CMAKE = "cmake"
    JSON = "json"
    XML = "xml"
    TEXT = "text"
    UNKNOWN = "unknown"


class SymbolType(StrEnum):
    """Kinds of structural symbols recorded in the index."""

    NAMESPACE = "namespace"
    CLASS = "class"
    STRUCT = "struct"
    INTERFACE = "interface"
    RECORD = "record"
    ENUM = "enum"
    ENUM_MEMBER = "enum_member"
    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    DESTRUCTOR = "destructor"
    PROPERTY = "property"
    FIELD = "field"
    EVENT = "event"
    DELEGATE = "delegate"
    TYPEDEF = "typedef"
    UNION = "union"
    MODULE = "module"


class Visibility(StrEnum):
    """Access level of a symbol where the language defines one."""

    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class ScanStatus(StrEnum):
    """Lifecycle state of an indexed file record."""

    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class IntegrityStatus(StrEnum):
    """Overall index health (PLAN.md §10.2)."""

    HEALTHY = "healthy"
    STALE = "stale"
    INCOMPLETE = "incomplete"
    WARNING = "warning"
    ERROR = "error"
    FAILED = "failed"


class RelationshipType(StrEnum):
    """Structural relationships recorded between symbols (PLAN.md §6.2)."""

    CONTAINS = "contains"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    CALLS = "calls"
    REFERENCES = "references"
    DECLARES = "declares"


class FindingSeverity(StrEnum):
    """Severity of an integrity finding (maps to error/warning counts)."""

    ERROR = "error"
    WARNING = "warning"

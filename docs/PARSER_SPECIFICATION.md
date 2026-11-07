# Parser Specification

Every language parser implements `cii.parsers.base.BaseParser` and returns the
same `ParseResult` (symbols, namespace declarations, relationship references,
issues), so the indexer and database layers are language-independent
(PLAN.md §8).

## Contract

```python
class BaseParser:
    def get_language(self) -> Language
    def get_parser_name(self) -> str        # e.g. "tree-sitter-cpp"
    def get_parser_version(self) -> str
    def supports(self, file_path: Path) -> bool
    def parse(self, file_path: Path, relative_path: str) -> ParseResult
```

`parse` never raises for content problems: failures are reported inside the
result (`ok=False` + `ParseIssue` with path, parser, reason, version,
timestamp) so callers retain previous index information (§8.4).

## Symbol identity

`fingerprint = SHA-256(type + fully-qualified name + signature)` — line
numbers are navigational metadata and never part of identity (§5.4).
Signatures are declaration headers (bodies stripped, whitespace-normalised,
capped at 300 chars). FQN separators: `::` for C/C++, `.` for C#/Python.

## Language coverage (v0.1)

| Category | C | C++ | C# | Python |
|---|---|---|---|---|
| Engine | tree-sitter-c | tree-sitter-cpp | tree-sitter-c-sharp | stdlib `ast` |
| Namespaces | – | nested + `a::b` compact | dotted + nested | – (module = file) |
| Classes/structs | struct, union | ✓ (+ templates) | class, struct, record | class (nested) |
| Interfaces | – | – | ✓ | – |
| Enums | ✓ | ✓ (incl. scoped) | ✓ | – |
| Functions | ✓ (overloads, decls) | ✓ (templates) | – | ✓ (async, nested) |
| Methods / ctors / dtors | – | ✓ | ✓ | ✓ (`__init__`/`__del__`) |
| Properties | – | – | ✓ | `@property` |
| Events / delegates | – | – | ✓ | – |
| Typedefs | ✓ | – | – | – |
| Inheritance evidence | – | base clauses | base list (1st = inherits, rest = implements @0.8) | base classes |
| Visibility | – | access specifiers | modifiers + C# defaults | UNKNOWN (no convention in spec) |
| Decorators | – | – | – | in signature |

Not extracted (outside §5.1/§8.2 scope): fields, enum members, global
variables, function bodies. Full docs of counting rules:
`cii/indexer/symbol_extractor.py` (§5.2: records count as classes, unions as
structures, ctors/dtors as methods).

## Error-node policy

Tree-sitter is error-tolerant: trees containing ERROR nodes still extract
what is structurally clear, and every such parse records an issue
("N syntax error node(s)") which surfaces in scan output and validation.
Python `SyntaxError` fails the parse entirely (`ok=False`).

## Extending

Register another `BaseParser` in `cii.parsers.registry.default_registry` —
the database schema and MCP interface do not change (§8.3). Planned: GLSL,
HLSL, CMake, Lua, JavaScript, TypeScript, Rust, Java, Go.

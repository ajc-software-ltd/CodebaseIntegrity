# MCP Interface

`cii mcp` serves the CII tools over stdio using the official Python MCP SDK v2
(`MCPServer`). Registered as a `local` server in OpenCode (`mcp.servers.cii` —
see OPENCODE_INTEGRATION.md). All responses are JSON.

## Tools (PLAN.md §12.1)

| Tool | Input | Returns |
|---|---|---|
| `index_status` | `{}` | project, file/symbol counts, files-by-status, health, last validation |
| `index_search` | `{query, symbol_type?, language?, limit?, offset?, expanded?}` | paginated symbol hits (concise by default) |
| `index_file` | `{path}` | one file's structural index (counts, namespaces, symbols) |
| `index_symbol` | `{name, file?}` | exact symbol lookup with metadata |
| `index_scan` | `{path?}` | synchronous incremental scan; scan id + operation status |
| `index_rebuild` | `{confirm}` | full rebuild (see below) |
| `index_validate` | `{full_scan}` | integrity status + findings |
| `index_dependencies` | `{symbol, relationship_types?}` | evidence-backed relationships (both directions) |
| `index_statistics` | `{}` | totals per language/type, recent scan performance |

## Resources (PLAN.md §12.2)

`cii://project/status`, `cii://project/index`, `cii://project/statistics`,
`cii://project/languages`, `cii://project/configuration` — read-only JSON
views of current database information.

## Error handling

CII failures return a structured payload instead of breaking the session:

```json
{ "error": { "type": "PathSecurityError", "message": "path escapes the project root: ..." } }
```

Unexpected failures are logged with their traceback and returned as
`{"error": {"type": "internal", ...}}`.

## Security (PLAN.md §12.3)

- Path arguments (`index_file.path`, `index_scan.path`, `index_symbol.file`)
  are validated: relative and traversal-free, or absolute but inside the
  project root. Violations are rejected with `PathSecurityError`.
- The LLM cannot modify source files through any tool; `index_scan` writes
  only inside `.cii/`.
- `index_rebuild` is destructive maintenance and requires `confirm: true`;
  the database is backed up first and a failed rebuild rolls back, preserving
  the previous index.
- No environment variables, secrets, or shell execution are exposed.

## Conventions

- `index_scan` executes synchronously and returns its `scan_id` (rows in
  `scan_history`).
- Search responses are paginated (`total`/`offset`/`limit`) and concise;
  `expanded: true` adds signatures, line numbers and freshness.
- `health` in `index_status` reflects index completeness cheaply; run
  `index_validate` for full filesystem comparison.

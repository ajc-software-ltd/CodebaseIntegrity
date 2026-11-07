# CII Architecture

Codebase Integrity & Intelligence is a standalone Python application with a
local MCP server, a CLI, a SQLite database, and an optional OpenCode
integration layer. It never modifies OpenCode's source code and never modifies
indexed projects' source files.

## Layer map

```text
CLI (cii)                 MCP server (cii mcp)        OpenCode plugin (optional)
        \                        |                        /
         \                       |                       /   (CLI only)
          +----------------------|----------------------+
                                 |
                        application.py        (orchestration:
                                 |             scan / rebuild / export)
        +------------+-----------+-----------+------------+
        |            |                       |            |
     scanner      indexer                integrity     monitoring
   (discovery,   (symbol sync,         (validator,   (watcher,
    hashing,      relationships,        duplicates,   debounce,
    changes)      markdown export)      health)       reconciliation)
        |            |                       |            |
        +------------+-----------+-----------+------------+
                                 |
                     database (SQLite, transactions)
                                 |
              parsers (tree-sitter C/C++/C#, Python ast)
```

## Data flow (scan cycle, PLAN.md §9.1)

1. **Discovery** walks the project tree applying exclusion, size, binary and
   generated-file policies; symlinks never leave the project root.
2. **Hashing** computes SHA-256 fingerprints (streamed); incremental scans
   trust size+mtime only as a fast path — content hashes stay authoritative.
3. **Change detection** classifies added/modified/deleted/renamed/unchanged
   (renames pair by identical hash).
4. **Transactional update** applies the change set; a pure rename keeps its
   `file_id` (and with it indexed symbols).
5. **Symbol indexing** parses changed files and *syncs* symbols
   identity-preservingly: unchanged symbols keep their `symbol_id`, so
   relationships from other files survive. Parser failures retain the previous
   index.
6. **Relationships** are rebuilt for reindexed files from parser evidence
   only (`contains`, `inherits`, `implements`).
7. **Export** regenerates `.cii/CODEBASE_INDEX.md` (skipped when unchanged).

## Information domains

- **Domain A (active development context)** belongs to the LLM session.
- **Domain B (persistent structural intelligence)** is CII's SQLite index.
  The LLM queries Domain B through MCP; CII — not the LLM — is the
  authoritative owner of the index (PLAN.md §2.2).

## Key design decisions

Full list with rationale: PLAN.md §26.1. Highlights:

- **stdlib `sqlite3`, no ORM** — transactions/savepoints and schema control
  without a dependency.
- **Savepoint transactions** — repository operations nest safely inside
  caller-scoped transactions; failed updates roll back completely.
- **Identity-preserving symbol sync** — reindexing never cascades away other
  files' relationships.
- **Errors as structured payloads on MCP** (`{"error": …}`) instead of
  session crashes; unexpected errors are logged with traceback.
- **MCP handlers run on worker threads** (SDK v2) — database access is
  serialised by a reentrant lock.
- **Deterministic validation** — reconciliation reuses hash-based change
  detection; no LLM interpretation anywhere in the pipeline.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `cii.core` | enums, domain models, configuration, exceptions |
| `cii.scanner` | discovery, filtering, hashing, change detection |
| `cii.parsers` | language extraction behind one `BaseParser` contract |
| `cii.indexer` | symbol sync, relationships, counting, Markdown export |
| `cii.database` | schema, migrations, repositories, transactions |
| `cii.integrity` | validation, reconciliation, duplicates, health |
| `cii.monitoring` | watcher, debounce, event processing, recovery |
| `cii.search` | symbol/file/relationship search, pagination |
| `cii.mcp` | MCP tools, resources, server |
| `cii.application` | scan/rebuild/export orchestration |
| `cii.cli` | Typer commands |

# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); milestones are
the release boundaries defined in PLAN.md §21.

## [0.9.0] — 2026-11-07

### Added — Milestone 09: MCP Server

- MCP server on the official Python SDK **v2** (`MCPServer`, stdio
  transport), served by `cii mcp`. Note: SDK v2 renamed FastMCP → MCPServer;
  API verified against the official v2 migration guide and live package.
- All nine tools per PLAN.md §12.1: `index_status`, `index_search`,
  `index_file`, `index_symbol`, `index_scan` (synchronous, returns scan id +
  status), `index_rebuild` (requires `confirm: true`; DB backup first,
  previous index preserved until success), `index_validate`, 
  `index_dependencies`, `index_statistics`.
- Five read-only resources per §12.2: `cii://project/{status,index,
  statistics,languages,configuration}` (JSON).
- Input validation & security (§12.3): all path arguments validated and
  confined to the project root (traversal rejected with structured errors);
  no filesystem writes outside `.cii/`; no shell execution; destructive
  maintenance gated behind explicit confirmation.
- Structured `{"error": {type, message}}` tool payloads for CII errors;
  unexpected failures are logged with traceback and returned as `internal`.
- Thread-safe database access: MCP v2 runs sync handlers on worker threads —
  `check_same_thread=False` + a reentrant lock serialising logical operations.
- CLI: `cii mcp`, `cii rebuild`, `cii statistics`.
- Tests: tool logic (25), in-process server, and a real external
  `ClientSession` stdio round-trip exercising every documented operation.

## [0.8.0] — 2026-11-07

### Added — Milestone 08: Search and Retrieval

- Symbol search (PLAN.md §11): name/FQN matching (exact ranks before
  substring), type and language filters, deterministic ordering, full
  pagination (`total`/`offset`/`limit`), concise results by default with
  optional expanded detail (signature, lines, freshness).
- Namespace attribution derived from recorded namespace declarations (longest
  FQN prefix) — schema stays as specified in §6.2.
- Namespace search and file search (filename/path fragment, language filter,
  pagination).
- Relationship queries: both directions for a symbol, optional type filter,
  evidence-backed results only (MCP `index_dependencies` shape).
- File structural overview (MCP `index_file` shape): counts, namespaces,
  symbols ordered by line, methods grouped by parent.
- CLI: `cii search` (`--type`, `--language`, `--limit`, `--offset`,
  `--expanded`, `--json`) and `cii file` (human + `--json`).

### Fixed

- `FileSearchHit` construction mismatched `scan_status`/`file_status` field
  names (runtime ValidationError) — caught by tests.

## [0.7.0] — 2026-11-07

### Added — Milestone 07: Incremental Monitoring

- Filesystem watcher (`watchfiles` inotify, config-driven directory
  exclusions) with injectable event source for deterministic tests.
- Debounce buffer: quiesce-based batching with a max-hold cap so busy writers
  cannot starve indexing (PLAN.md §9.2).
- Event processor: filters temporary/editor artefacts and out-of-project
  paths, triggers incremental rescans (hash fast-path skips unchanged files),
  skips scanning entirely for irrelevant batches.
- Periodic reconciliation (configurable interval) recovers from missed
  filesystem events (§18.3); startup behaviour per §9.3 (reconcile-first scan,
  no automatic full rebuild).
- New `[monitor]` configuration section (`debounce_seconds`,
  `max_debounce_seconds`, `reconcile_interval_seconds`).
- CLI: `cii watch [--max-seconds N]`.
- Live inotify integration test plus deterministic synthetic-source tests.

### Fixed

- Debounce buffer treated timestamp `0.0` as absent (falsy-zero bug) which
  disabled the max-hold path — caught by unit test.

## [0.6.0] — 2026-11-07

### Added — Milestone 06: Integrity Engine

- Read-only integrity validation (PLAN.md §10): deterministic findings, no LLM
  interpretation, never modifies source files or index records (verified by
  snapshot test and clean-venv run).
- Filesystem ↔ database reconciliation (reusing hash-based change detection,
  never trusting timestamps): unindexed / missing / changed-hash / renamed.
- Duplicate declaration detection (§10.4) distinguishing legitimate patterns:
  header/source declaration-definition pairs, overloads, C# partial classes;
  identical definitions in multiple sources = ERROR, conflicting type shapes =
  WARNING; Python cross-file comparisons excluded (file-local FQNs).
- Database consistency checks: SQLite integrity, foreign-key violations,
  schema version, failed/pending/unsupported file states, cross-file parent
  invariants.
- Full-scan validation: re-parses indexed files and reports symbol drift
  (`missing_symbols` / `new_symbols`) and unresolved relationship targets.
- Generated-Markdown freshness check (timestamp-insensitive comparison).
- Integrity status per §10.2 with documented precedence (ERROR > INCOMPLETE >
  STALE > WARNING > HEALTHY; FAILED on validation failure); persisted
  `integrity_reports` rows.
- CLI: `cii validate` / `cii validate --full` (human + `--json`).

## [0.5.0] — 2026-11-07

### Added — Milestone 05: Structural Indexer

- Index pipeline (parse → register → relationships → export, PLAN.md §9.1):
  per-file atomic indexing with `pending`/`failed` files picked up
  automatically; parser failures retain the previous valid index (§8.4).
- Identity-preserving symbol registration (`SymbolRepository.sync_for_file`):
  unchanged symbols keep their `symbol_id` across reindexes, so relationships
  from other files survive — verified by cross-file regression test.
- Relationship construction from parser evidence only: `contains` (nesting),
  `inherits`, `implements`; unresolved target names are counted and reported,
  never fabricated (`calls`/`references` remain future work per §22.1).
- Symbol counting derived from extracted symbols (§5.2 rules incl. record→class
  and union→structure folding).
- Markdown exporter: deterministic `.cii/CODEBASE_INDEX.md` (project
  statistics, per-file counts, namespaces, classes, methods grouped by parent,
  freshness timestamps; no source bodies), optional per-language split under
  `.cii/indexes/`; unchanged output is not rewritten.
- `Application` orchestration layer (`cii/application.py`) composing
  scan → index → export; CLI `cii scan` now runs the full pipeline and
  reports symbol deltas; new CLI `cii export`.

## [0.4.0] — 2026-11-07

### Added — Milestone 04: Parser Engine

- Parser contract (`BaseParser` → `ParseResult`): uniform symbols, namespace
  declarations, relationship references (evidence-based) and parse issues.
- Tree-sitter integration (0.26) with lazy grammar registry for C, C++, C#.
- C/C++ extraction: namespaces (nested + compact `a::b`), classes, structs,
  unions, enums, functions (incl. overloads and declarations), methods,
  constructors, destructors, templates, inheritance, access-modifier
  visibility, typedefs (C).
- C# extraction: namespaces (dotted + nested), classes, structs, interfaces,
  records, enums, methods, constructors, properties, events, delegates,
  base-list inherits/implements relationships, C# visibility defaults.
- Python extraction (stdlib `ast`): classes with inheritance, functions,
  methods, nested functions/classes, `__init__`/`__del__`, properties,
  static/class methods, decorators in signatures, async functions.
- Symbol fingerprints (SHA-256 of type + FQN + signature; line numbers
  excluded from identity per PLAN.md §5.4).
- Parser failure handling per §8.4: failures reported with reason/parser/
  version/timestamp and never destroy previous index data; tolerant extraction
  on trees with syntax-error nodes, with the errors reported as issues.
- Parser registry with the v0.1 language set; representative C++, C, C#, and
  Python fixtures with 43 parser tests.

### Notes

- Grammar API verified empirically (node types/fields differ from guesses:
  `base_class_clause`/`base_list` are named children, not fields).
- Fields, enum members and global variables are not extracted (outside the
  §8.2 categories); Python modules are represented by file records.

## [0.3.0] — 2026-11-07

### Added — Milestone 03: Scanner

- Project file discovery with configurable directory exclusions/inclusions,
  extension→language classification, max file size, binary detection
  (NUL-byte sniff), and conservative generated-file detection.
- Symlink policy: skipped by default; followed only when configured **and**
  resolving inside the project root; deterministic ancestor-chain cycle
  detection (path-based indexing preserved).
- Streaming SHA-256 content fingerprints (chunked, never loads whole files).
- Change detection: added / modified / deleted / renamed (hash-matched
  one-to-one) / unchanged, with content hashes as the authority and a
  size+mtime fast path for incremental scans (`--full` re-hashes everything).
- Transactional scan persistence: renames preserve `file_id` and any indexed
  symbols; failed scans leave the previous index intact; scan-history records
  per cycle.
- CLI: `cii scan` / `cii scan --full` (human + `--json`).

### Fixed

- `FileRepository.upsert` now updates `relative_path` when keyed by `file_id`
  (required for rename handling; caught by integration test).

## [0.2.0] — 2026-11-07

### Added — Milestone 02: Database

- SQLite database at `<project>/.cii/cii.db` (WAL mode, enforced foreign keys,
  busy timeout) with the full PLAN.md §6.2 schema: `projects`, `files`,
  `symbols`, `namespaces`, `relationships`, `scan_history`,
  `integrity_reports`, with indexes on searched columns.
- Versioned schema migrations (`PRAGMA user_version`), applied atomically;
  automatic backup of an existing database before upgrades.
- Repository layer: project registration (idempotent by root), file
  upsert/delete/lookup (incl. content-hash lookup for rename detection),
  atomic per-file symbol replacement with parent-link resolution, namespace
  declarations, evidence-backed relationships, scan history, integrity reports.
- Nesting-safe savepoint transactions — a failed update cannot leave a
  partially applied index.
- Database health checks: integrity check, foreign-key violations, schema
  version.
- CLI: `cii init` now creates the database and registers the project;
  new `cii status` command (human + `--json`).

## [0.1.0] — 2026-11-07

### Added — Milestone 01: Foundation

- Python package `cii` (src-layout) with `cii` console entry point.
- Core enums: `Language`, `SymbolType`, `Visibility`, `ScanStatus`,
  `IntegrityStatus`, `RelationshipType`.
- Core domain models: `SymbolInfo`, `FileRecord`, `SymbolCounts`, `IndexStatus`
  (Pydantic v2), with project-relative path enforcement.
- Configuration management: TOML project config (`.cii/config.toml`) deep-merged
  over built-in defaults; strict schema validation; `config/default.toml`
  reference copy kept in sync by test.
- Logging: `cii.*` logger namespace with console + rotating file handlers.
- Path security helpers: project-root containment, traversal rejection,
  symlink-escape rejection, relative POSIX path validation.
- Scoped TOML writer for configuration output (no extra dependency).
- CLI foundation: `cii --version`, `cii init`, `cii config` (human + `--json`).
- Pytest infrastructure with unit suites for configuration, models, paths,
  serialization, logging, and CLI.
- Ruff lint configuration.

### Notes

- Dependency compatibility verified on Python 3.14.9 for the planned stack:
  pydantic 2.14, typer 0.28, mcp SDK, tree-sitter 0.26 + C/C++/C# grammars,
  watchfiles 1.3 (install check only — runtime integration arrives with
  Milestones 04 and 07).

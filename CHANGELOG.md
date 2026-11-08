# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); milestones are
the release boundaries defined in PLAN.md §21.

## [1.0.5] — 2026-11-08

### Added

- README footnote: Windows is untested and undocumented by author policy;
  the project is intentionally Linux-designed, community Windows testing
  welcome.

## [1.0.4] — 2026-11-08

### Added

- README: OpenCode installation instructions (MCP registration, skill,
  auditor, AGENTS.md) placed above the Claude Code section.

## [1.0.3] — 2026-11-07

### Added

- Nine new languages (PLAN.md §8.3 complete): **GLSL, HLSL, CMake, Lua,
  JavaScript, TypeScript, Rust, Java, Go** — verified against live grammars
  and example files of every type. GLSL/HLSL reuse the C-family extractor;
  the rest run through a new spec-driven tree-sitter extractor (Go receivers,
  Rust impl/trait blocks, Lua dotted/colon methods, CMake function/macro
  defs, Java/Go packages, JS/TS constructors and heritage).
- Data-file tracking: **JSON, XML, TXT** (and .jsonl) are now indexed for
  presence with zero structural symbols — honest indexing, healthy validation.
- `CMakeLists.txt` recognised by exact file name (scanner + registry).
- 16 languages total; per-language example fixtures with extraction tests.

### Fixed

- Nested functions keep type `function` under function parents (only type
  parents promote to methods/constructors).
- Single-segment package declarations (`package app;`) scope the file.
- Missing grammar packages are reported as a failed file instead of crashing
  the scan.

## [1.0.2] — 2026-11-07

### Changed

- LICENSE: MIT with an additional restriction — the Software may not be sold
  or distributed commercially without prior written permission
  (licensing contact: ajc200x@gmail.com). `sell` removed from the MIT grant.

## [1.0.1] — 2026-11-07

### Added

- README: "Using CII with AI coding tools" — researched integration
  instructions for tools with **official MCP support**: OpenCode, Claude Code,
  Cursor, Windsurf, Cline, Goose, OpenHands (server registration + where each
  tool reads the CII workflow rules). Aider and Plandex are excluded: neither
  officially supports MCP.

### Removed

- README: milestone Status table (development complete; PLAN.md §21 remains
  the milestone record).

## [1.0.0] — 2026-11-07

### Added — Milestone 12: Reliability and Release

- Reliability test suite (PLAN.md §18): rebuild-from-source recovery after
  database loss, corrupt-database reporting (clear CII error, never silent
  wipe, never raw driver crash), backup-before-migration, break-then-fix
  parser failure recovery, failed-parse symbol retention.
- Security regression suite (§19): `.env`/secret files never opened or
  indexed (classification gate), out-of-root files never indexed, byte-level
  proof that scan/validate/rebuild never modify source files.
- `scripts/verify_installation.py` — end-to-end installation verification
  (version → init → scan → search → validate → export → status).
- `scripts/development.py benchmark` — synthetic multi-language benchmark
  (1000 files / 5000 symbols): all §17.1 targets met (status 4.7 ms,
  lookup 3.5 ms, search 3.4 ms; see docs/DEVELOPMENT_GUIDE.md).
- Completed documentation set: ARCHITECTURE, DATABASE_SCHEMA, MCP_INTERFACE,
  PARSER_SPECIFICATION, SECURITY, DEVELOPMENT_GUIDE.
- Release package: `uv build` (wheel + sdist); clean-venv wheel install
  verified — all installation checks pass.

### Verified

- The complete §20.5 acceptance scenario passed end-to-end (18 steps):
  multi-language scan, incremental reindexing, class addition, file deletion,
  duplicate detection, live OpenCode + MiMo locating an existing method,
  extending the existing class with **zero duplicates** (independently
  confirmed), index updated after development, accurate final validation.
- The `codebase-auditor` subagent ran live: symbol-by-symbol comparison
  against source, HEALTHY verdict in the specified report format.
- Definition of Done (PLAN.md §24) satisfied on Linux.

### Known limitations

- **Windows installation: NOT RUN** (no Windows host available). The code is
  platform-neutral (pathlib/os.scandir/stdlib sqlite3; watchfiles and the
  tree-sitter grammars support Windows) but this is unverified — remaining
  risk, see PLAN.md §26.1 item 17.

### Installation

- OS-level `cii` command documented and verified on CachyOS:
  `uv tool install --editable .` installs `cii` into `~/.local/bin`
  (verified: `cii --version` / `init` / `status` from a clean login shell).
- **Global OpenCode integration** (verified live, OpenCode v2.2.5):
  `opencode mcp add cii --global -- cii mcp` registers one auto-discovering
  server for all projects (degrades gracefully in un-indexed directories);
  the `codebase-integrity` skill and the hardened read-only
  `codebase-auditor` subagent install globally; CII rules go into the global
  `AGENTS.md` (hot-reloads); the primary agent delegates integrity audits to
  the auditor subagent via the `subagent` tool.

## [0.11.0] — 2026-11-07

### Added — Milestone 11: Automation and Plugin

- Optional OpenCode v2 plugin (`integrations/opencode/plugin/cii.ts` +
  README), built strictly on documented V2 APIs (`Plugin.define`, 
  `tool.hook("execute.before"/"execute.after")`, `session.hook("context")`,
  `tool.transform`, `command.transform`) — no undocumented internals.
- Detects development operations (edit/write/patch executions) and remembers
  changed files; contextual integrity reminders are injected into the model
  context while files await reindexing and cleared on `index_scan`/
  `index_rebuild`.
- Read-only `cii_status` tool and `/cii-audit` command that communicate with
  the standalone CII application **through the CLI only** — the plugin is not
  a second indexing engine and the MCP server remains fully operational
  without it (M09 acceptance runs had no plugin).
- Failure handling: 30 s CLI timeouts, guarded hook/registration setup,
  informative degradation when CII is missing — never breaks the session.
- Configurable launcher (`options.command`) for environments where `cii` is
  not on the service's PATH; `options.reminders` toggles the reminder hook.

### Verified (live, OpenCode v2.2.5)

- Plugin loads from `.opencode/plugins/` and via config with options.
- `cii_status` returns real index status through the CLI.
- Missing-CLI failure path degrades gracefully (verified accidentally, then
  intentionally).
- Contextual reminder verified: after a write-tool edit, the next model
  request carried the injected "CII integrity reminder" naming the exact file.
- `/cii-audit` registration is pinned by tests; headless slash-command
  dispatch was not observed (`opencode run` treats `/cmd` as prompt text —
  dispatch is the TUI's command facility). Its executor shares the proven
  `runCii` code path.

## [0.10.0] — 2026-11-07

### Added — Milestone 10: OpenCode Integration

- OpenCode v2 skill (`integrations/opencode/skills/codebase-integrity/SKILL.md`):
  the 10-step §15.2 workflow (check status → search before creating →
  retrieve source → avoid duplicates → refresh → validate → report honestly),
  loadable on demand.
- Integration instructions (`integrations/opencode/AGENTS.md`) with the six
  §15.3 rules: Structural Discovery, Source Verification, Duplicate
  Prevention, Index Integrity, Post-Development, Failure.
- Read-only `codebase-auditor` subagent
  (`integrations/opencode/agents/codebase-auditor.md`): permissions deny
  edit/write/shell; covers the eight §15.4 responsibilities.
- `cii opencode-config`: installer command generating the proposed OpenCode v2
  MCP registration snippet with resolved paths (python `-m cii` launcher;
  no global-executable assumption) plus placement explanation — it never
  edits OpenCode configuration itself.
- `docs/OPENCODE_INTEGRATION.md`: complete install/verify guide with the
  verified `mcp.servers` v2 snippet.

### Verified (live, OpenCode v2.2.5)

- `opencode mcp list` shows the `cii` server **connected** from project-level
  config (both `opencode.json` and `.opencode/opencode.json` placements).
- Tool discovery and the MiMo development workflow proven end-to-end in a
  headless `opencode run` session: the agent loaded the `codebase-integrity`
  skill, called `index_status` → `index_scan` → `index_search`, retrieved the
  correct source file, and reported integrity without modifying anything.
- No user OpenCode configuration was modified (verification ran in a temp
  project directory).

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

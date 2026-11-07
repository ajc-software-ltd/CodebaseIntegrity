# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/); milestones are
the release boundaries defined in PLAN.md §21.

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

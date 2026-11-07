# Database Schema

Authoritative store: `<project>/.cii/cii.db` (SQLite, WAL mode, enforced
foreign keys). Generated Markdown is derived output — the database is the
source of truth. Schema follows PLAN.md §6.2 exactly.

## Schema version

Tracked in `PRAGMA user_version` (`SCHEMA_VERSION` in
`cii/database/migrations.py`, currently **1**). Migrations are plain SQL
scripts applied atomically (BEGIN … version bump … COMMIT); an existing
database is copied to `cii.db.backup-v<N>` before an upgrade. A database from
a newer CII build is refused.

## Tables

### projects
| Column | Type | Notes |
|---|---|---|
| project_id | TEXT PK | UUID |
| project_name | TEXT | |
| project_root | TEXT | unique in practice (registration key) |
| created_at | REAL | unix time |
| last_scan | REAL | nullable |
| index_version | TEXT | generated index format version |
| configuration_hash | TEXT | SHA-256 of the effective config TOML |

### files
| Column | Type | Notes |
|---|---|---|
| file_id | INTEGER PK | preserved across renames |
| project_id | TEXT FK → projects | ON DELETE CASCADE |
| relative_path | TEXT | POSIX separators; UNIQUE(project_id, relative_path) |
| filename, extension, language | TEXT | |
| content_hash | TEXT | SHA-256 fingerprint (indexed) |
| file_size, modified_at, last_scanned | | |
| scan_status | TEXT | `pending` / `indexed` / `failed` / `unsupported` |
| parser_version | TEXT | |

### symbols
| Column | Type | Notes |
|---|---|---|
| symbol_id | INTEGER PK | stable across reindexes when identity unchanged |
| file_id | INTEGER FK → files | ON DELETE CASCADE |
| parent_symbol_id | INTEGER FK → symbols | ON DELETE SET NULL |
| symbol_name, fully_qualified_name | TEXT | |
| symbol_type | TEXT | see `SymbolType` |
| visibility | TEXT | |
| signature | TEXT | declaration header, no bodies |
| start_line, end_line | INTEGER | navigational only, not identity |
| fingerprint | TEXT | SHA-256 of type + FQN + signature (§5.4) |

Indexes: `file_id`, `symbol_name`, `fully_qualified_name`, `symbol_type`.

### namespaces
Per-file namespace **declarations** (a namespace spanning files produces one
row per declaring file). `parent_namespace_id` records nesting within a file.

### relationships
| Column | Notes |
|---|---|
| source_symbol_id, target_symbol_id | FK → symbols, CASCADE |
| relationship_type | `contains` / `inherits` / `implements` (v1) |
| confidence | parser evidence strength (0–1) |
| resolution_status | `resolved` |
| UNIQUE(source, target, type) | duplicates return the existing row |

Only evidence-backed relationships are stored; unresolved target names are
counted and reported, never invented (the schema requires a real target).

### scan_history
One row per scan cycle: type (`full`/`incremental`), timestamps, file and
symbol counters, status.

### integrity_reports
One row per validation run: time, files checked, error/warning counts,
resulting status.

## Recovery semantics

- All writes go through savepoint transactions (`cii.database.transactions`);
  a failed scan rolls back completely.
- Symbol replacement is identity-preserving (`SymbolRepository.sync_for_file`):
  unchanged symbols keep their ids and relationships.
- Database destroyed? `cii init` + `cii scan` rebuilds everything from source
  (verified in `tests/integration/test_reliability.py`).
- Corrupt database? Opening reports a clear `DatabaseError`/`MigrationError`;
  it is never silently wiped.

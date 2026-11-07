# Development Guide

## Setup

```bash
uv sync                       # installs runtime + dev dependencies
uv run pytest                 # test suite
uv run ruff check src tests   # lint (line length 100, py312)
```

Requires Python ≥ 3.12 (developed and tested on 3.14.9). Layout: `src/cii/`
package, `tests/{unit,integration,parsers,database,mcp}`, `integrations/`
OpenCode artifacts, `scripts/` developer tooling.

## Commands

| Command | Purpose |
|---|---|
| `cii init` | create `.cii/`, config, database, register project |
| `cii scan [--full]` | incremental scan → index → export |
| `cii status` / `cii statistics` | health & counts / structural statistics |
| `cii search Q [...]` / `cii file P` | symbol search / file structure |
| `cii validate [--full]` | integrity findings (read-only) |
| `cii rebuild` | full rebuild with backup |
| `cii export` | regenerate `CODEBASE_INDEX.md` |
| `cii watch [--max-seconds N]` | live filesystem monitoring |
| `cii mcp` | MCP server (stdio) |
| `cii opencode-config` | proposed OpenCode registration snippet |

All accept `--root`; query commands accept `--json`.

## Testing strategy

- **unit**: configuration, models, paths, search, debounce, counting, resolver,
  duplicate detection, health precedence, plugin contract.
- **parsers**: representative C++, C, C#, Python fixtures (§20.2 categories)
  including invalid files.
- **database**: schema lifecycle, migrations (atomic failure, backups),
  repositories, savepoint transactions.
- **integration**: scan cycles, indexer pipeline, integrity validation,
  watcher (incl. a live inotify test), reliability/recovery, MCP tools and a
  real external MCP client over stdio.
- Performance tests are a script, not pytest (see below) — timing assertions
  in CI would be flaky.

## Benchmark results (2026-11-07, Ryzen 5 5600X, 1000 files / 5000 symbols)

| Operation | Median | §17.1 target | Verdict |
|---|---|---|---|
| full scan (first) | 11.7 s | scales with size | — |
| incremental scan (no changes) | 135 ms | proportional | — |
| `index_status` | 4.7 ms | < 100 ms | within target |
| single-file symbol lookup | 3.5 ms | < 100 ms | within target |
| symbol search | 3.4 ms | < 250 ms | within target |
| Markdown export | 60 ms | proportional | — |
| `index_validate` (quick) | 261 ms | — | — |

Reproduce with `python scripts/development.py benchmark --files 1000`.

## Release process

1. Bump `__version__` in `src/cii/__init__.py` (single source; hatchling
   reads it).
2. Update `CHANGELOG.md` and PLAN.md §26.
3. `uv run pytest && uv run ruff check src tests`.
4. `python scripts/verify_installation.py` — end-to-end install check.
5. `uv build` → `dist/*.whl` + `dist/*.tar.gz`; verify a clean-venv wheel
   install.
6. Commit as `CII: MNN - …` (signed). Tagging/publishing is the owner's call.

## Conventions

- Type annotations on public interfaces; docstrings explain intent.
- No ORM, no unnecessary dependencies (§3.1 "avoid unnecessary dependencies").
- Every parser output flows through `ParseResult`; never bypass it.
- Never edit `config/default.toml` without updating the code defaults (the
  sync test enforces both directions).
- Failures are reported, never swallowed; validation is read-only.

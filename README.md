# Codebase Integrity & Intelligence (CII)

A standalone, local-first developer infrastructure tool that gives AI coding
agents a persistent, continuously maintained **structural index** of software
projects — what exists and where — so they stop losing track of existing code,
duplicating functionality, or breaking established components.

**The LLM decides what to build. CII establishes what already exists. The
source code remains the ultimate authority.**

See [PLAN.md](PLAN.md) for the full engineering specification.

## What CII records

For every indexed source file: namespaces, classes, structs, interfaces,
enums, functions, methods, properties, symbol relationships, symbol counts,
file fingerprints and index validation state.

CII never stores complete source files in its index. When an agent needs to
understand an implementation, CII identifies the relevant file and symbol so
the agent can retrieve the actual source.

## Features (planned — see PLAN.md milestones)

- Persistent SQLite structural index per project (`<project>/.cii/cii.db`).
- Multi-language symbol extraction (C, C++, C#, Python first).
- Incremental scanning with content-hash change detection.
- Integrity validation: stale records, missing files, duplicate declarations.
- Fast structural search through a local MCP server for OpenCode v2.
- Generated Markdown index (`.cii/CODEBASE_INDEX.md`).
- Standalone CLI — works without OpenCode.

## Installation

Requires Python 3.12+.

```bash
git clone <this repository>
cd CodebaseIntegrity
uv sync            # or: pip install -e .
```

This installs the `cii` command into the environment.

## Quick start

```bash
cd /path/to/your/project
cii init           # creates .cii/ and the project configuration
cii config         # show the effective configuration
cii --version
```

`cii init` never modifies your files; it only creates the `.cii/` data
directory. Add `.cii/` to your project's `.gitignore` (the command prints a
recommended entry).

## Development

```bash
uv sync                  # install with dev dependencies
uv run pytest            # run the test suite
uv run ruff check src tests   # lint
```

Project structure, milestones and acceptance criteria: [PLAN.md](PLAN.md).
Changelog: [CHANGELOG.md](CHANGELOG.md).

## Status

Milestone progress is tracked in PLAN.md §21 and the CHANGELOG.

| Milestone | Scope | State |
|---|---|---|
| M01 | Foundation (package, config, logging, core models, CLI) | done |
| M02 | Database (SQLite schema, repositories, migrations) | done |
| M03 | Scanner (discovery, hashing, change detection) | done |
| M04 | Parser engine (C, C++, C#, Python extraction) | done |
| M05 | Structural indexer (symbols, relationships, Markdown export) | done |
| M06 | Integrity engine (validation, duplicates, reconciliation) | done |
| M07 | Incremental monitoring (watcher, debounce, recovery) | done |
| M08 | Search & retrieval (symbols, files, relationships, pagination) | done |
| M09–M12 | MCP server → 1.0 release | pending |

## License

TBD — to be decided by the project owner.

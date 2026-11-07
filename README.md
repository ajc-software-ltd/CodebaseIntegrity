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

## Features

- Persistent SQLite structural index per project (`<project>/.cii/cii.db`).
- Multi-language symbol extraction (C, C++, C#, Python first).
- Incremental scanning with content-hash change detection.
- Integrity validation: stale records, missing files, duplicate declarations.
- Fast structural search through a local MCP server for OpenCode v2.
- Generated Markdown index (`.cii/CODEBASE_INDEX.md`).
- Standalone CLI — works without OpenCode.

## Installation

Requires Python 3.12+.

**OS-wide `cii` command (recommended):**

```bash
git clone https://github.com/ajc-software-ltd/CodebaseIntegrity
cd CodebaseIntegrity
uv tool install --editable .     # installs `cii` into ~/.local/bin
```

This makes `cii` available in every terminal (CachyOS/Arch: `~/.local/bin` is
on the default PATH). The editable install reflects source updates
immediately. Remove with `uv tool uninstall codebase-integrity`.

**Project-local (development):**

```bash
uv sync            # or: pip install -e .
```

This installs `cii` into the project's `.venv` only (`uv run cii …`).

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

## Using CII with AI coding tools

CII integrates through two portable mechanisms — its **MCP server** (`cii mcp`,
which auto-discovers the nearest `.cii/` from its working directory) and the
**workflow rules** in `integrations/opencode/AGENTS.md` (tool-agnostic text —
copy it wherever your tool keeps instructions). Every tool below supports MCP
natively; nothing requires third-party adapters. In directories without a CII
index the tools answer "run cii init" instead of failing.

OpenCode · Claude Code · Cursor · Windsurf · Cline · Goose · OpenHands

### Claude Code

```bash
claude mcp add --transport stdio cii -- cii mcp      # add: --scope user for all projects
```

Project-shared alternative: `.mcp.json` in the project root:

```json
{ "mcpServers": { "cii": { "type": "stdio", "command": "cii", "args": ["mcp"] } } }
```

Claude Code reads `AGENTS.md` as project instructions when no `CLAUDE.md`
exists (or import it from one). It also supports the CII skill and the
read-only auditor natively: `skills/codebase-integrity/SKILL.md` and
`agents/codebase-auditor.md` under `.claude/`.

### Cursor

Create `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

```json
{ "mcpServers": { "cii": { "command": "cii", "args": ["mcp"] } } }
```

Instructions: put the `integrations/opencode/AGENTS.md` rules in `AGENTS.md`
at the project root (Cursor reads it automatically, including nested files),
or use `.cursor/rules/*.mdc` for more control.

### Windsurf

Add under `mcpServers` in `~/.codeium/windsurf/mcp_config.json` (or use the
MCP Marketplace / Settings → Cascade → MCP Servers):

```json
{ "mcpServers": { "cii": { "command": "cii", "args": ["mcp"] } } }
```

Instructions: `.windsurf/rules/*.md` (or `.windsurf/global_rules.md`) at the
workspace root — drop the `integrations/opencode/AGENTS.md` content there.

### Cline

```bash
cline mcp add cii --yes -- cii mcp
```

Or edit `~/.cline/data/settings/cline_mcp_settings.json` (same `mcpServers`
shape as above). Instructions: Cline auto-detects a root `AGENTS.md` — or use
`.clinerules/` / `.cline/rules/` directories.

### Goose

Add to `~/.config/goose/config.yaml` (or `goose configure` → Add Extension →
Command-Line):

```yaml
extensions:
  cii:
    name: CII
    type: stdio
    cmd: cii
    args: [mcp]
    enabled: true
    timeout: 300
```

Instructions: Goose reads `AGENTS.md` by default; `.goosehints` files
(project, or global `~/.config/goose/.goosehints`) work too.

### OpenHands

In Agent Canvas: `Customize > MCP Servers` → `Add custom server` → type
**STDIO**, Name `cii`, Command `cii`, Arguments `mcp` (saved in
`~/.openhands/settings.json`; SDK users pass the equivalent `mcp_config`).
Instructions: OpenHands loads the repository's `AGENTS.md` into the agent's
context — put the CII rules there.

### Portable tips

- The CII MCP server's `instructions` reach most MCP clients automatically,
  so the basic workflow survives even without rules files.
- A root `AGENTS.md` carrying the five CII rules (Structural Discovery,
  Source Verification, Duplicate Prevention, Post-Development, Failure)
  serves every tool above; source it from `integrations/opencode/AGENTS.md`.
- Keep the tool's text-only surface in mind: `cii scan` / `cii validate` work
  as ordinary shell commands too, so tools without MCP can still use CII via
  their terminal.

## How it works

CII maintains one thing: a persistent **structural index** — the answer to
"what does this codebase already contain, and where?" That answer lives in a
database on disk, so it survives the end of a conversation, context
compaction, and IDE restarts. An AI agent consults the index *before* writing
code (so it extends what exists instead of duplicating it) and refreshes it
*after* (so the next session starts accurate).

### The lifecycle of a project

```text
cii init   →   cii scan   →   [code changes]   →   cii scan   →   cii validate
  once            first            …loop…          incremental      read-only
```

1. **`cii init`** (once per project) creates `.cii/` and registers the
   project:

   ```text
   your-project/.cii/
   ├── cii.db             ← the authoritative index (SQLite)
   ├── CODEBASE_INDEX.md  ← generated readable view of the index
   ├── config.toml        ← your overrides (exclusions, limits, output…)
   ├── cache/             ← database backups
   └── logs/
   ```

2. **`cii scan`** is the workhorse. Each run:
   - walks the tree, skipping everything that is not yours to index
     (`.git/`, `node_modules/`, build outputs, binaries, generated files,
     `.env`-style secrets — all configurable in `config.toml`);
   - hashes file contents (SHA-256) and compares with the database to find
     exactly what **changed** — added, modified, renamed (matched by hash),
     deleted. Unchanged files cost almost nothing (milliseconds on a
     1000-file project);
   - parses only the changed files (C, C++, C#, Python) and records their
     symbols — classes, functions, methods, properties, namespaces — plus
     relationships (inheritance, containment) in `cii.db`;
   - regenerates `CODEBASE_INDEX.md`.

   A file that fails to parse is marked failed and its previous index entry is
   **kept**, never destroyed. `cii scan --full` re-verifies everything.

3. **Query it** whenever you wonder what exists:

   ```bash
   cii search initialize          # all implementations, with file + class
   cii file src/audio/miniaudio.cpp   # one file's structure
   cii status                     # health + counts
   cii statistics                 # project-wide breakdown
   ```

4. **`cii validate`** (read-only) checks that the index still matches reality:
   unindexed/missing/changed/renamed files, duplicate declarations, failed
   parses, stale generated output. `--full` re-parses and diffs every symbol.
   It reports findings — it never fixes or deletes anything itself.

5. **`cii watch`** keeps everything current automatically (filesystem events,
   debounced; periodic reconciliation recovers events that were missed).
   `cii rebuild` reconstructs the index from source (with a database backup
   first) if it is ever lost or corrupted.

### How AI agents consume it

Register the MCP server once per project (see
[docs/OPENCode_INTEGRATION.md](docs/OPENCode_INTEGRATION.md)); the agent then
gets tools like `index_search`, `index_file`, `index_scan`, `index_validate`.
With the bundled `codebase-integrity` skill, a coding task flows like this:

```text
user: "add a shutdown() method to the audio engine"
agent: index_search("shutdown")            ← does it already exist?
       index_search("AudioEngine")         ← where is the class?
       reads the real source file          ← index proves existence, source
       extends the EXISTING class            proves behaviour
       index_scan                          ← index updated
       index_validate                      ← integrity confirmed
       reports: files modified 1, duplicates none, validation healthy
```

The index is evidence, not instruction: the source code stays the ultimate
authority, and if CII is unavailable the agent must say so rather than claim
the codebase was checked. The optional OpenCode plugin adds reminders
("N files changed since the last index refresh") and a `/cii-audit` command,
but everything works without it.

## Development

```bash
uv sync                  # install with dev dependencies
uv run pytest            # run the test suite
uv run ruff check src tests   # lint
```

Project structure, milestones and acceptance criteria: [PLAN.md](PLAN.md).
Changelog: [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).

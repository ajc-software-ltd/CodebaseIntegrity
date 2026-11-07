# OpenCode v2 Integration

How to connect CII to OpenCode v2. CII never modifies OpenCode's source code
and never edits existing OpenCode configuration — the installer prints a
**proposed** snippet (`cii opencode-config`) and this page explains where it
belongs; you apply it yourself.

## Global setup (all projects, all agents)

Everything below is optional per-project; this section installs CII for
**every** OpenCode session on the machine. Verified live against OpenCode
v2.2.5.

1. **OS-level command** — `uv tool install --editable .` (see README), so
   `cii` resolves from any directory.

2. **Global MCP registration** — one entry serves every project because the
   server auto-discovers the nearest `.cii/` from its working directory
   (local MCP servers start in the workspace), and degrades gracefully in
   un-indexed directories (tools answer "run cii init"):

   ```bash
   opencode mcp add cii --global -- cii mcp
   ```

   Verify: `opencode mcp list` shows `✓ cii connected` in any directory.

3. **Global skill** — so any agent can load the workflow on demand:

   ```bash
   cp -r integrations/opencode/skills/codebase-integrity ~/.config/opencode/skills/
   ```

4. **Global read-only auditor subagent** — launchable by the primary agent
   (via the `subagent` tool) after substantial changes or when validation
   reports findings. Its permissions deny-all-first and allow only read-only
   capabilities, so mutation tools (`index_scan`/`index_rebuild`) are
   structurally impossible for it:

   ```bash
   cp integrations/opencode/agents/codebase-auditor.md ~/.config/opencode/agents/
   ```

5. **Global instructions** — add the CII rules (from
   `integrations/opencode/AGENTS.md`) to `~/.config/opencode/AGENTS.md`, so
   every session in an indexed project follows Structural Discovery / Source
   Verification / Duplicate Prevention / Post-Development / Failure discipline.
   AGENTS.md edits hot-reload into running sessions.

6. **Primary agent delegation** — tell your primary agent (e.g. in its agent
   file) to delegate independent integrity audits to the `codebase-auditor`
   subagent at appropriate times (post-change verification, before completion
   reports, when `index_validate` reports errors).

The MCP server's own `instructions` are injected into every session's system
prompt automatically, so the basic workflow survives even without the skill.

## 1. Register the MCP server

CII exposes its tools through a local MCP server on stdio (`cii mcp`).
Add it to the project-level configuration of the project you want indexed
(`opencode.json` or `.opencode/opencode.json` in that project):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",

  "mcp": {
    "servers": {
      "cii": {
        "type": "local",
        "command": ["/path/to/project/.venv/bin/cii", "mcp", "--root", "/path/to/project"],
        "enabled": true,
        "timeout": 30000
      }
    }
  }
}
```

Notes:

- With a global install (`uv tool install --editable .` from the CII
  repository) the command is simply `["cii", "mcp", "--root", "/path/to/project"]`.
- Without one, the snippet deliberately uses an **absolute path to the
  project's virtual environment** (or `python -m cii mcp`) — do not assume a
  global `cii` executable exists. `cii opencode-config` prints the exact
  command for the current machine.
- Run `cii init` in the project first; the server refuses uninitialised
  projects.
- Configuration changes apply without restarting OpenCode.

Run `cii opencode-config` in the indexed project to generate this snippet with
resolved paths, including an alternative launcher through the project's
Python interpreter:

```jsonc
"command": ["/path/to/project/.venv/bin/python", "-m", "cii", "mcp", "--root", "/path/to/project"]
```

## 2. Install the skill (optional, recommended)

Copy the skill so coding agents discover the CII workflow on demand:

```bash
cp -r integrations/opencode/skills/codebase-integrity <project>/.opencode/skills/
```

The skill instructs the agent to check index status, search before creating
code, retrieve source before modifying it, refresh and validate the index
after development, and report integrity honestly. It is loaded on demand —
it does not inflate every conversation.

## 3. Install the integration instructions

Merge `integrations/opencode/AGENTS.md` into the project's `AGENTS.md` (or
reference it via the `instructions` config field). It defines the Structural
Discovery, Source Verification, Duplicate Prevention, Index Integrity,
Post-Development and Failure rules.

## 4. Install the codebase-auditor subagent (optional)

```bash
cp integrations/opencode/agents/codebase-auditor.md <project>/.opencode/agents/
```

The auditor is a strictly read-only subagent (its permissions deny edit and
shell): it inspects index health, finds missing files, duplicate symbols and
stale entries, and reports discrepancies with recommended corrections.

## 5. Verify

1. `opencode mcp list` — the `cii` server should show as connected.
2. Ask the agent: "Use the CII skill to find implementations of X" — it
   should call `index_search` and retrieve the correct source file.
3. Ask it to extend an existing class — it should not create a duplicate.

## Security notes

- The MCP tools are read-only with respect to your source files; `index_scan`
  writes only inside `.cii/`; `index_rebuild` requires explicit confirmation
  and backs up the database first.
- All tool paths are confined to the project root; path traversal is rejected.
- CII never indexes `.env` files (by exclusion), binary files, or content
  outside the project root.

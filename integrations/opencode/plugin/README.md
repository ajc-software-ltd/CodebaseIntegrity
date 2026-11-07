# CII OpenCode plugin (optional)

Workflow glue between OpenCode and the standalone CII application
(PLAN.md §15.5). **Optional** — the CII MCP server remains fully operational
without it. This plugin is not a second indexing engine: it never parses or
indexes anything itself and reaches CII only through the documented CLI.

## What it does

| Feature | Mechanism |
|---|---|
| Detect development operations | `tool.hook("execute.after")` on `edit`/`write`/`patch` remembers changed files |
| Contextual integrity reminders | `session.hook("context")` adds a system reminder while files await reindexing; cleared when `index_scan`/`index_rebuild` runs |
| CII status information | adds a read-only `cii_status` tool that runs `cii status --json` |
| Post-development validation | adds a `/cii-audit` command that runs `cii validate --json` and posts the result to the session |

## Install

```bash
mkdir -p <project>/.opencode/plugins
cp integrations/opencode/plugin/cii.ts <project>/.opencode/plugins/
```

Or register it from anywhere via `opencode.json(c)`:

```jsonc
{
  "plugins": [
    { "package": "../path/to/plugin", "options": { "command": ["/path/to/.venv/bin/cii"] } }
  ]
}
```

## Options

| Option | Default | Meaning |
|---|---|---|
| `command` | `["cii"]` | Launcher for the CII CLI. Use an absolute path (or `["python", "-m", "cii"]`) if `cii` is not on PATH — do not assume a global executable. |
| `reminders` | `true` | Set to `false` to disable the contextual reminder hook. |

## Failure handling

- Every CLI invocation runs with a 30 s timeout and captured output; failures
  are reported as tool/command text, never thrown into the session.
- If CII is not installed, `cii_status` and `/cii-audit` return an informative
  message; the rest of OpenCode is unaffected.
- Hook or registration failures are logged (`[cii plugin] …`) and skipped; the
  plugin never blocks session startup.

## Notes

- OpenCode loads `.opencode/plugins/*.ts` automatically (V2 plugin API:
  default export via `Plugin.define({ id, setup })`).
- The plugin targets the V2 API only; for V1 compatibility see the official
  "Support V1" pattern in the OpenCode plugins documentation.

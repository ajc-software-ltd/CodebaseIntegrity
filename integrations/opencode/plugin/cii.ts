// CII OpenCode plugin — optional workflow glue for Codebase Integrity &
// Intelligence (PLAN.md §15.5).
//
// This plugin is deliberately thin: it is NOT a second indexing engine. All
// indexing is done by the standalone CII application, which this plugin
// reaches only through the supported CLI interface. The CII MCP server works
// fully without this plugin.
//
// Responsibilities:
//   - detect development operations (edit/write/patch tool executions) and
//     remember the changed files;
//   - provide contextual integrity reminders in the model context while files
//     are awaiting reindexing;
//   - expose CII status information as a `cii_status` tool;
//   - coordinate post-development validation via the `/cii-audit` command.
//
// Failure handling: every CLI invocation is guarded with timeouts and error
// capture; a missing CII installation degrades to an informative message and
// never breaks the session.

import { Plugin } from "@opencode/plugin"
import { execFile } from "node:child_process"

interface CiiPluginOptions {
  /** Launcher for the CII CLI. Defaults to ["cii"] (must be on PATH). */
  command?: string[]
  /** Skip the contextual reminder hook. */
  reminders?: boolean
}

const EDIT_TOOLS = new Set(["edit", "write", "patch", "multiedit"])
const REFRESH_TOOLS = /index_scan|index_rebuild/

function extractPath(input: unknown): string | undefined {
  if (input == null || typeof input !== "object") return undefined
  const record = input as Record<string, unknown>
  for (const key of ["filePath", "path", "file", "filename"]) {
    const value = record[key]
    if (typeof value === "string" && value.length > 0) return value
  }
  return undefined
}

function runCii(command: string[], args: string[], cwd: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const [launcher, ...base] = command
    execFile(
      launcher,
      [...base, ...args],
      { cwd, timeout: 30_000, maxBuffer: 4 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(`${command.join(" ")} ${args.join(" ")}: ${error.message}`))
          return
        }
        resolve(stdout.toString())
      },
    )
  })
}

export default Plugin.define({
  id: "cii",
  async setup(ctx) {
    const options = (ctx.options ?? {}) as CiiPluginOptions
    const command = options.command ?? ["cii"]
    const directory = ctx.location.directory
    const changed = new Map<string, number>()
    const note = (message: string) => console.warn(`[cii plugin] ${message}`)

    // 1. Detect development operations: remember changed source files.
    try {
      await ctx.tool.hook("execute.before", (event) => {
        if (REFRESH_TOOLS.test(event.tool)) {
          // An index refresh was requested — reminders are no longer needed.
          changed.clear()
        }
      })
      await ctx.tool.hook("execute.after", (event) => {
        if (!EDIT_TOOLS.has(event.tool)) return
        const path = extractPath(event.input)
        if (path) changed.set(path, Date.now())
      })
    } catch (error) {
      note(`tool hooks unavailable: ${String(error)}`)
    }

    // 2. Contextual integrity reminders (system instruction augmentation).
    if (options.reminders !== false) {
      try {
        await ctx.session.hook("context", (event) => {
          if (changed.size === 0) return
          const files = [...changed.keys()].slice(0, 20)
          event.system.push({
            type: "text",
            text:
              `CII integrity reminder: ${changed.size} file(s) changed since the last ` +
              `index refresh (${files.join(", ")}${changed.size > files.length ? ", …" : ""}). ` +
              "Before relying on the structural index, refresh it with the CII " +
              "index_scan tool; after finishing, run index_validate and report the result. " +
              "Do not create new classes or functions without first searching the index.",
          })
        })
      } catch (error) {
        note(`context hook unavailable: ${String(error)}`)
      }
    }

    // 3. Expose CII status information as a tool (read-only).
    try {
      await ctx.tool.transform((editor) => {
        editor.add({
          name: "cii_status",
          description:
            "Show the CII structural index status of this project (health, file and " +
            "symbol counts). Read-only; use the CII MCP tools for search and scanning.",
          input: {
            type: "object",
            properties: {},
            additionalProperties: false,
          },
          execute: async () => {
            try {
              const stdout = await runCii(command, ["status", "--root", directory, "--json"], directory)
              return { content: stdout.trim() }
            } catch (error) {
              return {
                content:
                  `CII status unavailable: ${String(error)}. ` +
                  "Ensure CII is installed (see docs/OPENCode_INTEGRATION.md) and " +
                  "that 'cii init' has been run in this project.",
              }
            }
          },
        })
      })
    } catch (error) {
      note(`tool registration unavailable: ${String(error)}`)
    }

    // 4. Coordinate post-development validation via /cii-audit.
    try {
      await ctx.command.transform((editor) => {
        editor.add({
          name: "cii-audit",
          description: "Run CII integrity validation and report the result",
          execute: async ({ sessionID }) => {
            let text: string
            try {
              const stdout = await runCii(command, ["validate", "--root", directory, "--json"], directory)
              text = `CII audit result:\n${stdout.trim()}`
            } catch (error) {
              text = `CII audit unavailable: ${String(error)} (structural verification could NOT be performed).`
            }
            await ctx.session.synthetic({ sessionID, text })
          },
        })
      })
    } catch (error) {
      note(`command registration unavailable: ${String(error)}`)
    }
  },
})

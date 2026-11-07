---
name: Codebase Integrity
description: Use the CII structural index before and after code changes - discover existing implementations, avoid duplicates, keep the index current, and report integrity. Load before substantial development work in an indexed project.
---

# Codebase Integrity (CII) workflow

CII maintains a persistent structural index of this project (what exists and
where). The index is advisory evidence: the source code remains the authority.

## Before development

1. **Check index status** — call `index_status` before substantial work. If
   health is not `healthy`, run `index_validate` and understand why before
   relying on the index.
2. **Search for existing implementations** — call `index_search` (and
   `index_symbol` for exact names) before creating any class, function or
   method. Look for the capability under several names, not just the name you
   plan to use.
3. **Identify relevant files and symbols** — use `index_file` to see a file's
   structure (classes, methods, counts) and `index_dependencies` to see known
   relationships.
4. **Retrieve the actual source** — the index proves *that* something exists,
   not *how* it works. Read the real source file before modifying or extending
   existing functionality.

## During development

5. **Do not duplicate implementations** — if equivalent functionality exists,
   extend it (or call it) instead of adding another implementation, even under
   a different filename or namespace.
6. **Respect established structure** — keep new code inside the namespaces and
   classes that own that responsibility. If new functionality belongs in an
   existing class, extend that class.

## After development

7. **Run the project's tests** after your modifications.
8. **Refresh the index** — call `index_scan` so changed files are reindexed.
9. **Validate** — call `index_validate` and confirm the result.
10. **Report integrity honestly** — include the index status and validation
    result in your completion report. If any step failed or was skipped, say
    so; never claim the codebase is integrity-checked when it is not. Report
    unresolved findings (duplicates, stale entries) instead of silently fixing
    or ignoring them.

## Tool summary

| Tool | Purpose |
|---|---|
| `index_status` | Index health and counts |
| `index_search` | Find symbols by name (filters, pagination) |
| `index_symbol` | Exact symbol lookup with metadata |
| `index_file` | One file's structural index |
| `index_dependencies` | Known relationships for a symbol |
| `index_scan` | Incremental reindex (after edits) |
| `index_validate` | Integrity findings (read-only) |
| `index_statistics` | Project-level counts and scan performance |
| `index_rebuild` | Full rebuild — destructive, requires `confirm: true` |

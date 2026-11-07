# AGENTS.md — CII integration instructions

These instructions apply in projects indexed by Codebase Integrity &
Intelligence (CII). They establish how coding agents must interact with the
structural index.

## Structural Discovery Rule

Before creating a class, function or method, inspect the CII index for
existing equivalents (`index_search`, `index_symbol`, `index_file`). If the
capability already exists, extend or reuse it.

## Source Verification Rule

The index identifies what exists but does not prove how an implementation
works. Retrieve the actual source before modifying or extending existing
functionality.

## Duplicate Prevention Rule

Do not create another implementation merely because an existing symbol has a
different filename or namespace. Check fully qualified names and
`index_dependencies` before concluding that something is missing.

## Index Integrity Rule

Never manually fabricate or edit index records. All index changes must
originate from successful parsing and database operations (`index_scan`,
`index_rebuild`). Do not hand-edit `.cii/` contents.

## Post-Development Rule

After source modifications, ensure the changed files have been indexed
(`index_scan`) and validation has completed (`index_validate`) before
reporting the task complete.

## Failure Rule

If CII is unavailable (server down, project not initialised, tool errors),
clearly report that structural verification could not be performed. Do not
claim that the codebase has been integrity-checked.

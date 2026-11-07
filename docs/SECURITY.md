# Security

CII is a local developer tool. Its security posture is filesystem safety
(PLAN.md §19): operate inside a configured project root, never modify source
files, treat all source content as data — never as instructions.

## Boundaries and verification status

| # | Requirement (§19) | Implementation | Verified by |
|---|---|---|---|
| 1 | Operate within an explicit project root | every path resolves via `require_within_root` | `tests/unit/test_paths.py`, MCP tool tests |
| 2 | Reject path traversal | `validate_relative_path` rejects `..`, absolute and Windows-style paths | `test_paths.py`, `tests/mcp/` |
| 3 | Avoid reading `.env` files and secret stores | files are classified by extension **before any content is read**; `.env` has no parser mapping and is skipped at discovery (never opened) | `test_reliability.py::test_env_files_are_never_indexed_or_read` |
| 4 | Exclude private keys and credentials | same classification gate: `.pem`/`.key`/etc. have no mapping | `test_discovery.py` (unsupported extensions counted, never read) |
| 5 | Never index binary files | NUL-byte sniff after classification; binaries skipped | `test_file_filter.py`, `test_discovery.py` |
| 6 | Avoid following external symlinks | symlinks skipped by default; even when enabled, targets must resolve inside the root; deterministic cycle guard | `test_discovery.py` |
| 7 | Restrict database access to the project | one DB per project at `.cii/cii.db`; no cross-project access | architecture |
| 8 | Do not execute indexed source code | parsers parse text only; nothing imports/executes indexed content | design; `test_reliability.py::test_mcp_tools_do_not_modify_source_files` |
| 9 | Do not modify source files | CII writes only inside `.cii/`; MCP exposes no modification tools | `test_reliability.py` (byte-level source comparison across scan/validate/rebuild) |
| 10 | Keep MCP tools to documented operations | nine tools, five read-only resources; destructive rebuild gated on `confirm: true` | `tests/mcp/` |

## Prompt-injection posture

All source content — comments, documentation, filenames — is **data**, never
instructions. The parsers extract structural facts only; nothing in indexed
content can influence CII's behaviour or security policies. (Consuming LLMs
remain responsible for how they treat source text they retrieve.)

## Secrets handling

CII never emits credential values. It stores no secrets: the database
contains structural metadata only. Configuration files carry no credentials.

## Destructive operations

- `index_rebuild` (MCP + CLI): requires explicit confirmation on MCP; creates
  a timestamped database backup; runs inside a transaction — a failed rebuild
  preserves the previous index (verified in `test_tools.py`).
- Schema migrations: atomic; existing databases are backed up first.

## Residual risks

- Content-based secret detection (e.g. a credential pasted into a `.py`
  file) is out of scope — such files are legitimately indexed as source;
  the Markdown export contains signatures and names only, never bodies.
- File classification is extension-based by design; renaming a secret to
  `secrets.py` would index its *structure*. Projects should keep secrets out
  of source trees.

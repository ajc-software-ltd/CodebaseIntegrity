# PLAN.md
# Codebase Integrity & Intelligence (CII)

**Project:** Codebase Integrity & Intelligence  
**Abbreviation:** CII  
**Product Type:** Developer Infrastructure / Local AI Coding Intelligence  
**Version:** 0.1.0  
**Status:** Initial Development Specification  
**Primary Integration:** OpenCode v2  
**Primary LLM:** MiMo 2.6 Pro  
**Primary Runtime:** Python  
**Database:** SQLite  
**Protocol:** Model Context Protocol (MCP)  
**Architecture:** Modular, local-first, language-independent

---

# 1. Project Overview

## 1.1 Purpose

Codebase Integrity & Intelligence (CII) is a standalone developer infrastructure application designed to provide AI coding agents with a persistent, continuously maintained structural understanding of software projects.

Its primary purpose is to prevent AI coding agents from losing track of existing code, duplicating functionality, creating conflicting implementations, or unnecessarily modifying established components.

CII achieves this through a persistent structural index containing:

- Source filenames and paths.
- Namespaces.
- Classes and structures.
- Functions.
- Methods.
- Interfaces.
- Enumerations.
- Properties.
- Relevant symbol relationships.
- Symbol counts.
- File fingerprints.
- Index validation information.

The system does not need to store entire source files in its structural index.

Instead, it records what exists and where it exists.

When an AI agent needs to understand an implementation, CII identifies the relevant source file and symbol so that the agent can retrieve the actual source code.

## 1.2 Primary Objective

Develop a reusable codebase intelligence system that allows an AI coding agent to maintain persistent structural awareness independently of its active conversation and working context.

The system must provide two logically separated information domains:

**Domain A — Active Development Context**

Contains the current task, instructions, planning, implementation reasoning, source code being examined, debugging information and development history.

**Domain B — Persistent Structural Intelligence**

Contains a continuously updated representation of the actual project structure, including filenames, namespaces, classes, functions and methods.

These are logical information domains, not two independently allocated model contexts.

The LLM retrieves information from Domain B through MCP whenever required.

This architecture must work across different LLMs and coding agents.

## 1.3 Core Objectives

1. Maintain an accurate structural index of an entire software project.
2. Automatically discover source files and programming symbols.
3. Detect additions, modifications, renames and deletions.
4. Prevent duplicate class and function implementations.
5. Identify existing functionality before new development begins.
6. Provide fast structural searches through MCP.
7. Validate the index against the actual filesystem.
8. Support multiple programming languages.
9. Persist project knowledge between OpenCode sessions.
10. Minimise unnecessary context consumption.
11. Remain independent of OpenCode's internal implementation.
12. Provide a reusable architecture for future coding agents.

---

# 2. Product Architecture

CII must be developed as a standalone Python application with independent internal modules.

The application must expose its functionality through:

1. A local MCP server.
2. A command-line interface.
3. A persistent SQLite database.
4. An automatically generated Markdown index.
5. An optional OpenCode plugin.
6. OpenCode skills and agent instructions.

The application must not require modifications to OpenCode's source code.

## 2.1 Architectural Overview

```text
                  OPENCode v2
                       |
                 MiMo 2.6 Pro
                       |
              Primary Coding Agent
                       |
          +------------+-------------+
          |                          |
     ACTIVE CONTEXT            STRUCTURAL CONTEXT
          |                          |
   Current development          CII MCP Server
   Source examination                 |
   Planning                     +-----+------+
   Implementation               |            |
   Debugging                  SEARCH       INDEX
   Testing                      |            |
                              SCANNER    DATABASE
                                 |            |
                                 +-----+------+
                                       |
                                 SQLITE DATABASE
                                       |
                            GENERATED CODEBASE INDEX
                                       |
                              INTEGRITY VALIDATOR
```

## 2.2 Separation of Responsibilities

The LLM must never be the authoritative owner of the structural index.

CII is responsible for determining what actually exists.

The LLM is responsible for interpreting the index and deciding what development action is appropriate.

The scanner is responsible for extracting symbols.

The database is responsible for retaining structural information.

The validator is responsible for detecting discrepancies.

The MCP server is responsible for making this information available to OpenCode.

---

# 3. Technology Stack

## 3.1 Primary Technologies

| Component | Technology |
|---|---|
| Main application | Python 3.12+ |
| MCP implementation | Official Python MCP SDK |
| Database | SQLite |
| Database access | SQLAlchemy or native SQLite |
| Initial parser framework | Tree-sitter |
| C/C++ semantic analysis | Clang tooling |
| C# semantic analysis | Roslyn |
| Python parser | Python AST |
| Filesystem monitoring | Watchfiles |
| CLI | Typer |
| Data validation | Pydantic |
| Logging | Python logging |
| Configuration | TOML |
| Testing | Pytest |
| Packaging | Pyproject.toml |

Dependencies must be selected based on compatibility and maintenance status at implementation time.

Avoid unnecessary dependencies.

## 3.2 Development Environment

Primary development environment:

- Linux.
- CachyOS.
- Python.
- OpenCode v2.
- JetBrains Rider.
- Git.
- MiMo 2.6 Pro.

Windows compatibility must remain a design requirement.

CII must not depend on Linux-specific filesystem behaviour.

---

# 4. Repository Structure

Create the following project structure.

```text
CodebaseIntegrity/
│
├── PLAN.md
├── README.md
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── .gitignore
│
├── config/
│   └── default.toml
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATABASE_SCHEMA.md
│   ├── MCP_INTERFACE.md
│   ├── PARSER_SPECIFICATION.md
│   ├── OPENCODE_INTEGRATION.md
│   ├── SECURITY.md
│   └── DEVELOPMENT_GUIDE.md
│
├── src/
│   └── cii/
│       │
│       ├── __init__.py
│       ├── main.py
│       ├── application.py
│       │
│       ├── core/
│       │   ├── models.py
│       │   ├── enums.py
│       │   ├── configuration.py
│       │   ├── exceptions.py
│       │   └── events.py
│       │
│       ├── scanner/
│       │   ├── scanner.py
│       │   ├── discovery.py
│       │   ├── file_filter.py
│       │   ├── file_hash.py
│       │   └── change_detector.py
│       │
│       ├── parsers/
│       │   ├── base.py
│       │   ├── registry.py
│       │   │
│       │   ├── treesitter/
│       │   │   ├── parser.py
│       │   │   └── language_registry.py
│       │   │
│       │   ├── cpp/
│       │   │   ├── parser.py
│       │   │   └── clang_analyzer.py
│       │   │
│       │   ├── csharp/
│       │   │   ├── parser.py
│       │   │   └── roslyn_analyzer.py
│       │   │
│       │   └── python/
│       │       └── parser.py
│       │
│       ├── indexer/
│       │   ├── indexer.py
│       │   ├── symbol_extractor.py
│       │   ├── symbol_resolver.py
│       │   ├── relationship_builder.py
│       │   └── markdown_exporter.py
│       │
│       ├── database/
│       │   ├── database.py
│       │   ├── models.py
│       │   ├── repositories.py
│       │   ├── migrations.py
│       │   └── transactions.py
│       │
│       ├── integrity/
│       │   ├── validator.py
│       │   ├── reconciliation.py
│       │   ├── duplicate_detector.py
│       │   ├── consistency_checker.py
│       │   └── health.py
│       │
│       ├── monitoring/
│       │   ├── watcher.py
│       │   ├── event_processor.py
│       │   └── debounce.py
│       │
│       ├── search/
│       │   ├── symbol_search.py
│       │   ├── file_search.py
│       │   └── relationship_search.py
│       │
│       ├── mcp/
│       │   ├── server.py
│       │   ├── tools.py
│       │   ├── resources.py
│       │   └── schemas.py
│       │
│       ├── cli/
│       │   ├── commands.py
│       │   └── output.py
│       │
│       └── utilities/
│           ├── paths.py
│           ├── logging.py
│           └── serialization.py
│
├── integrations/
│   └── opencode/
│       │
│       ├── skills/
│       │   └── codebase-integrity/
│       │       └── SKILL.md
│       │
│       ├── agents/
│       │   └── codebase-auditor.md
│       │
│       ├── AGENTS.md
│       │
│       └── plugin/
│           ├── cii.ts
│           └── README.md
│
├── templates/
│   ├── CODEBASE_INDEX.md
│   └── project-config.toml
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── parsers/
│   ├── database/
│   ├── mcp/
│   └── fixtures/
│
└── scripts/
    ├── development.py
    └── verify_installation.py
```

This structure is the target architecture. Files must be created progressively as their corresponding modules are implemented.

---

# 5. Structural Index System

This is the most important component of CII.

The structural index must provide an accurate and lightweight representation of the source code.

## 5.1 Index Requirements

Every indexed source file must record:

- Relative filename.
- Relative directory.
- File extension.
- Programming language.
- Namespace declarations.
- Classes.
- Structures.
- Interfaces.
- Enumerations.
- Functions.
- Methods.
- Properties.
- Symbol counts.
- File fingerprint.
- Last successful scan.

The index must not store complete source files.

It must not automatically store function bodies or large documentation comments.

The primary objective is structural discovery.

## 5.2 Example Structural Index

The following is the expected readable output.

```text
PROJECT: VulkanOne

INDEX_VERSION: 1.0

LAST_UPDATED: 2026-11-07

FILE: src/audio/miniaudio.cpp

LANGUAGE: C++

[COUNTS]
Namespaces: 1
Classes: 1
Structures: 0
Functions: 2
Methods: 4
Properties: 0
Enums: 0

[NAMESPACES]
miniaudio

[FUNCTIONS]
initaudio
stopaudio

[CLASSES]
miniaudio

[METHODS]
miniaudio:
    create_device
    destroy_device
    start_playback
    stop_playback
```

Counts must be generated from actual extracted symbols.

They must never be inferred or manually entered by the LLM.

## 5.3 Nested Symbol Support

The index must distinguish between:

- Global functions.
- Namespace functions.
- Class methods.
- Static methods.
- Constructors.
- Destructors.
- Nested classes.
- Nested namespaces.

Example:

```text
FILE: VulkanRenderer.cpp

[NAMESPACE]
VulkanOne::Rendering

[CLASS]
VulkanRenderer

[METHODS]
VulkanRenderer:
    VulkanRenderer
    ~VulkanRenderer
    initialize
    shutdown
    begin_frame
    end_frame
    present

[CLASS]
VulkanDevice

[METHODS]
VulkanDevice:
    create
    destroy
    wait_idle
```

## 5.4 Symbol Identity

Symbol names alone are insufficient to identify symbols reliably.

Each symbol must have a stable identity within its file and project.

The internal identity should include:

- Project identifier.
- File identifier.
- Fully qualified symbol name.
- Symbol type.
- Parent symbol.
- Signature fingerprint where available.

This allows the system to distinguish between overloaded functions and methods with identical names in different classes.

Line numbers may be stored as navigational metadata, but they must not be considered stable identity because source modifications can move declarations.

---

# 6. Database Architecture

SQLite will be the authoritative persistent storage system.

Markdown indexes will be generated from SQLite.

## 6.1 Database Location

Each indexed project should contain its own CII data directory.

Default:

```text
ProjectRoot/
│
└── .cii/
    ├── cii.db
    ├── CODEBASE_INDEX.md
    ├── config.toml
    ├── cache/
    └── logs/
```

The `.cii` directory must be excluded from the scanner itself.

Database files must not be committed to Git by default.

The generated Markdown index may be optionally committed according to project configuration.

## 6.2 Required Tables

### Projects

Stores project-level information.

Fields:

- project_id
- project_name
- project_root
- created_at
- last_scan
- index_version
- configuration_hash

### Files

Stores discovered files.

Fields:

- file_id
- project_id
- relative_path
- filename
- extension
- language
- content_hash
- file_size
- modified_at
- last_scanned
- scan_status
- parser_version

### Symbols

Stores extracted programming symbols.

Fields:

- symbol_id
- file_id
- parent_symbol_id
- symbol_name
- fully_qualified_name
- symbol_type
- visibility
- signature
- start_line
- end_line
- fingerprint

### Namespaces

Stores namespace information.

Fields:

- namespace_id
- file_id
- namespace_name
- parent_namespace_id

### Relationships

Stores known structural relationships.

Fields:

- relationship_id
- source_symbol_id
- target_symbol_id
- relationship_type
- confidence
- resolution_status

Examples:

- contains
- inherits
- implements
- calls
- references
- declares

Relationships must only be recorded when supported by parser or semantic-analysis evidence.

### ScanHistory

Records scanning operations.

Fields:

- scan_id
- project_id
- scan_type
- started_at
- completed_at
- files_processed
- files_failed
- symbols_added
- symbols_updated
- symbols_removed
- status

### IntegrityReports

Stores validation results.

Fields:

- report_id
- project_id
- validation_time
- files_checked
- errors_found
- warnings_found
- report_status

## 6.3 Database Requirements

- Use transactions for index updates.
- Enforce foreign-key constraints.
- Index frequently searched columns.
- Support database migrations.
- Prevent partially completed updates.
- Use WAL mode where appropriate.
- Support safe database recovery.
- Never delete valid existing records before a replacement scan succeeds.

A failed scan must not corrupt the previous valid index.

---

# 7. Scanner Architecture

The scanner discovers source files and determines which files require indexing.

## 7.1 File Discovery

The scanner must:

1. Identify the project root.
2. Enumerate eligible files.
3. Determine their language.
4. Apply exclusion rules.
5. Calculate file hashes.
6. Compare hashes with the database.
7. Queue new or changed files for parsing.

## 7.2 Excluded Directories

Default exclusions should include:

```text
.git/
.cii/
.venv/
venv/
node_modules/
__pycache__/
.cache/
build/
dist/
out/
bin/
obj/
cmake-build-debug/
cmake-build-release/
generated/
third_party/
vendor/
```

These exclusions must be configurable.

Generated files and third-party libraries should not be indexed by default.

The user must be able to explicitly include them.

## 7.3 File Filtering

Support configurable:

- File extensions.
- Directory exclusions.
- Directory inclusions.
- Maximum file sizes.
- Binary-file detection.
- Symlink handling.
- Generated-file detection.

Do not follow symbolic links outside the project root unless explicitly authorised.

## 7.4 Change Detection

Use SHA-256 or an equivalent cryptographic content fingerprint.

A file is considered modified when its content fingerprint differs from the indexed fingerprint.

Do not rely exclusively on timestamps.

Detect:

- New files.
- Modified files.
- Deleted files.
- Renamed files.
- Moved files.
- Unsupported files.

Renames should be detected using matching content hashes where possible.

---

# 8. Parser Architecture

CII must support multiple programming languages through a common parser interface.

All parsers must return the same internal symbol representation.

## 8.1 Parser Interface

Define a common parser contract.

Conceptual interface:

```python
class BaseParser:

    def supports(self, file_path):
        ...

    def parse(self, file_path):
        ...

    def extract_symbols(self, syntax_tree):
        ...

    def get_language(self):
        ...
```

Implementations must follow this contract or an equivalent strongly typed interface.

## 8.2 Initial Language Support

Version 0.1 should prioritise:

### C++

Extract:

- Namespaces.
- Classes.
- Structs.
- Enums.
- Functions.
- Member functions.
- Constructors.
- Destructors.
- Templates.
- Inheritance.
- Access modifiers.

Use Tree-sitter for initial structural extraction.

Introduce Clang-based semantic analysis when needed for more reliable C++ resolution.

### C

Extract:

- Functions.
- Structs.
- Unions.
- Enums.
- Typedefs.
- Global declarations.
- Namespaces where applicable through C++ compatibility.

### C#

Extract:

- Namespaces.
- Classes.
- Structs.
- Interfaces.
- Records.
- Enums.
- Methods.
- Constructors.
- Properties.
- Events.
- Delegates.
- Inheritance.
- Implemented interfaces.

Use Tree-sitter for initial extraction and Roslyn for deeper semantic analysis.

### Python

Extract:

- Modules.
- Classes.
- Functions.
- Methods.
- Nested functions.
- Decorators.
- Properties.
- Class inheritance.

Use Python AST.

## 8.3 Future Language Support

The parser architecture must allow future extensions without changing the database or MCP interfaces.

Planned languages:

- GLSL.
- HLSL.
- CMake.
- Lua.
- JavaScript.
- TypeScript.
- Rust.
- Java.
- Go.

## 8.4 Parser Failure Handling

A parser failure must not result in the deletion of previously valid index information.

The system must record:

- File path.
- Parser used.
- Failure reason.
- Parser version.
- Timestamp.
- Whether the previous index was retained.

Unsupported syntax must be reported rather than silently ignored.

---

# 9. Incremental Indexing

Full-project scanning after every modification is inefficient.

CII must implement incremental indexing.

## 9.1 Incremental Process

```text
Filesystem Event
      |
      v
Identify Changed File
      |
      v
Calculate File Hash
      |
      v
Compare Existing Hash
      |
      +---- Unchanged ----> Ignore
      |
      v
Parse Changed File
      |
      v
Extract Symbols
      |
      v
Validate Parse Result
      |
      v
Transactional Database Update
      |
      v
Regenerate Affected Index Output
```

## 9.2 Monitoring

Use Watchfiles or an equivalent reliable filesystem monitoring implementation.

The watcher should:

- Detect changes.
- Debounce rapid successive writes.
- Ignore temporary editor files.
- Avoid processing incomplete writes.
- Queue changed files.
- Retry transient failures.
- Recover from missed filesystem events using periodic reconciliation.

The watcher must not continuously consume excessive CPU resources.

## 9.3 Startup Behaviour

On initialisation:

1. Open the project database.
2. Verify the database schema.
3. Check the project identity.
4. Inspect index health.
5. Identify unindexed files.
6. Identify changed files.
7. Schedule required scans.
8. Start filesystem monitoring.

A full rebuild must not occur on every OpenCode connection.

---

# 10. Integrity Validation

Integrity validation is a core feature, not an optional enhancement.

CII must determine whether the stored structural index matches the actual source code.

## 10.1 Validation Rules

Detect:

- Missing indexed files.
- Newly created unindexed files.
- Deleted source files.
- Renamed files.
- Changed file hashes.
- Missing symbols.
- Newly created symbols.
- Duplicate declarations.
- Unresolved relationships.
- Parser failures.
- Stale index records.
- Database inconsistencies.

## 10.2 Integrity Status

Use the following statuses:

```text
HEALTHY
    Index matches the latest successful scan.

STALE
    One or more files have changed since indexing.

INCOMPLETE
    Some eligible files have not been successfully indexed.

WARNING
    Non-critical inconsistencies have been detected.

ERROR
    Structural inconsistencies require investigation.

FAILED
    The validation operation could not complete.
```

Do not report HEALTHY if files failed parsing or validation was incomplete.

## 10.3 Reconciliation

The reconciliation system must compare:

1. Filesystem state.
2. Database records.
3. Extracted parser output.
4. Generated Markdown index.

Reconciliation must be deterministic.

It must not depend on LLM interpretation.

## 10.4 Duplicate Detection

Detect potential duplicate:

- Function names.
- Class names.
- Fully qualified symbols.
- Function signatures.
- Class declarations.

Distinguish between:

- Legitimate overloads.
- Header declarations and source definitions.
- Multiple implementations.
- Forward declarations.
- Partial classes.
- Duplicate definitions.

Do not automatically delete or modify duplicate source code.

Produce findings for the LLM to investigate.

---

# 11. Search and Retrieval System

The search engine is responsible for making structural information accessible without requiring the LLM to read the entire index.

## 11.1 Search Requirements

Support searches by:

- Filename.
- File path.
- Namespace.
- Class.
- Function.
- Method.
- Symbol type.
- Fully qualified name.
- Parent class.
- Programming language.

## 11.2 Search Examples

Request:

```text
Find all implementations of initialize.
```

Expected response:

```text
RESULTS: 3

VulkanRenderer.cpp
    Class: VulkanRenderer
    Method: initialize

AudioEngine.cpp
    Class: AudioEngine
    Method: initialize

WindowManager.cpp
    Class: WindowManager
    Method: initialize
```

Request:

```text
Show the structure of miniaudio.cpp.
```

Expected response:

```text
FILE: src/audio/miniaudio.cpp

LANGUAGE: C++

NAMESPACE: miniaudio

CLASSES: 1
FUNCTIONS: 2
METHODS: 4

FUNCTIONS:
    initaudio
    stopaudio

CLASS:
    miniaudio

METHODS:
    create_device
    destroy_device
    start_playback
    stop_playback
```

## 11.3 Search Results

Every result should contain:

- File path.
- Symbol name.
- Symbol type.
- Namespace.
- Parent class where applicable.
- Signature where available.
- Line location where available.
- Index freshness information.

Search results must remain concise by default.

Provide optional expanded results when the LLM needs more information.

---

# 12. MCP Server

The MCP server is the primary OpenCode integration.

It must run locally and communicate through the standard MCP transport supported by OpenCode.

Use the official Python MCP SDK.

## 12.1 MCP Tool Design

Implement the following tools.

### Tool 1: index_status

Purpose:

Return the current health and status of the project index.

Input:

```json
{}
```

Output:

- Project name.
- Project root.
- Indexed file count.
- Indexed symbol count.
- Last successful scan.
- Pending files.
- Failed files.
- Index health.
- Index version.

### Tool 2: index_search

Purpose:

Search indexed symbols.

Input:

```json
{
  "query": "initialize",
  "symbol_type": "method",
  "language": "cpp",
  "limit": 20
}
```

All optional filters must be supported.

### Tool 3: index_file

Purpose:

Return the structural index of a specific file.

Input:

```json
{
  "path": "src/audio/miniaudio.cpp"
}
```

Output must contain the filename, namespace, classes, functions, methods and counts.

### Tool 4: index_symbol

Purpose:

Locate a specific symbol and its structural metadata.

Input:

```json
{
  "name": "initialize",
  "file": "src/renderer/VulkanRenderer.cpp"
}
```

### Tool 5: index_scan

Purpose:

Schedule an incremental scan.

Input:

```json
{
  "path": "src/audio/miniaudio.cpp"
}
```

If no path is supplied, scan all detected changes.

Return a scan identifier and operation status.

### Tool 6: index_rebuild

Purpose:

Perform a complete project index rebuild.

Input:

```json
{
  "confirm": true
}
```

The rebuild must preserve the previous valid database until the replacement scan has completed successfully.

### Tool 7: index_validate

Purpose:

Run integrity validation.

Input:

```json
{
  "full_scan": true
}
```

Return errors, warnings and discrepancies.

### Tool 8: index_dependencies

Purpose:

Retrieve known relationships for a symbol.

Input:

```json
{
  "symbol": "VulkanRenderer",
  "relationship_types": [
    "contains",
    "inherits",
    "calls"
  ]
}
```

Only return relationships supported by available evidence.

### Tool 9: index_statistics

Purpose:

Provide project-level structural statistics.

Return:

- Total source files.
- Files per language.
- Total classes.
- Total functions.
- Total methods.
- Total interfaces.
- Total enums.
- Total namespaces.
- Indexing performance.
- Parser failures.

## 12.2 MCP Resources

Where supported by the MCP SDK, expose read-only resources:

```text
cii://project/status
cii://project/index
cii://project/statistics
cii://project/languages
cii://project/configuration
```

These resources must return current database information.

## 12.3 MCP Security

- Restrict operations to the configured project root.
- Do not allow arbitrary filesystem access.
- Validate all paths.
- Reject path traversal.
- Do not expose environment variables or secrets.
- Do not execute arbitrary shell commands.
- Do not expose source-code modification tools.
- Keep the index read-only to the LLM.
- Require explicit confirmation for destructive maintenance operations.

MCP indexing tools must never modify original project source files.

---

# 13. Command-Line Interface

CII must operate independently of OpenCode.

The CLI provides manual control, diagnostics and development access.

Proposed commands:

```bash
cii init
```

Initialise CII in the current project.

```bash
cii scan
```

Perform an incremental scan.

```bash
cii scan --full
```

Perform a complete scan.

```bash
cii status
```

Display index health.

```bash
cii search initialize
```

Search for a symbol.

```bash
cii file src/audio/miniaudio.cpp
```

Display a file's structural information.

```bash
cii validate
```

Validate the index.

```bash
cii rebuild
```

Rebuild the index.

```bash
cii export
```

Regenerate CODEBASE_INDEX.md.

```bash
cii statistics
```

Display project statistics.

```bash
cii mcp
```

Start the MCP server using stdio transport.

The CLI must provide useful human-readable output and optional machine-readable JSON output.

---

# 14. Generated Markdown Index

CII must generate a readable structural reference.

Default output:

```text
.cii/CODEBASE_INDEX.md
```

## 14.1 Requirements

The Markdown file must:

- Be generated from SQLite.
- Never be manually maintained.
- Contain no complete source-code implementations.
- Include project statistics.
- Organise entries by file.
- List namespaces.
- List classes and methods.
- List functions.
- Display symbol counts.
- Include index freshness information.

## 14.2 Large Projects

For large projects, avoid placing the entire index into the LLM's context.

Support:

```text
.cii/
    CODEBASE_INDEX.md
    indexes/
        cpp.md
        csharp.md
        python.md
        shaders.md
```

The exporter should generate language-specific indexes when useful.

The database remains authoritative.

The LLM should retrieve the relevant file or symbol through MCP instead of reading every Markdown index.

---

# 15. OpenCode v2 Integration

OpenCode integration must be developed as a separate integration layer.

Do not modify OpenCode's source code.

Do not automatically overwrite the user's existing OpenCode configuration.

The installer must generate a proposed configuration snippet and explain where it belongs.

## 15.1 MCP Registration

Provide an example project-level configuration for OpenCode v2.

Use the current v2 configuration structure:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",

  "mcp": {
    "servers": {
      "cii": {
        "type": "local",
        "command": [
          "cii",
          "mcp"
        ],
        "enabled": true,
        "timeout": 30000
      }
    }
  }
}
```

The installed executable must resolve correctly through the user's environment.

An alternative launcher may use the project's Python environment.

The installer must not assume that a global `cii` executable exists.

## 15.2 OpenCode Skill

Create:

```text
.opencode/skills/codebase-integrity/SKILL.md
```

The skill must instruct the coding agent to:

1. Check index status before substantial development.
2. Search for existing implementations.
3. Identify relevant files and symbols.
4. Retrieve source files before modifying them.
5. Avoid duplicate implementations.
6. Respect established namespaces and class ownership.
7. Run tests after modifications.
8. Request an index refresh.
9. Validate the index after development.
10. Report unresolved integrity issues.

The skill should be loaded on demand rather than injecting the complete CII manual into every conversation.

## 15.3 AGENTS.md

Create an integration instruction file.

It must establish these rules:

**Structural Discovery Rule**

Before creating a class, function or method, inspect the CII index for existing equivalents.

**Source Verification Rule**

The index identifies what exists but does not prove how an implementation works. Retrieve the actual source before modifying or extending existing functionality.

**Duplicate Prevention Rule**

Do not create another implementation merely because an existing symbol has a different filename or namespace.

**Index Integrity Rule**

Never manually fabricate or edit index records.

**Post-Development Rule**

After source modifications, ensure that the changed files have been indexed and validation has completed.

**Failure Rule**

If CII is unavailable, clearly report that structural verification could not be performed. Do not claim that the codebase has been integrity-checked.

## 15.4 Codebase Auditor Agent

Create:

```text
.opencode/agents/codebase-auditor.md
```

The auditor should be a read-only subagent.

Its responsibilities:

- Inspect index health.
- Identify missing files.
- Find potential duplicate symbols.
- Identify stale entries.
- Check namespace consistency.
- Compare index records with actual source declarations.
- Report discrepancies.
- Recommend corrective action.

It must not modify source code or the database.

## 15.5 OpenCode Plugin

Develop the plugin as a later integration milestone.

Location:

```text
.opencode/plugins/cii.ts
```

The plugin may use OpenCode's supported lifecycle hooks to improve integration.

Potential responsibilities:

- Detect development operations.
- Mark changed files as requiring reindexing.
- Provide contextual integrity reminders.
- Coordinate post-development validation.
- Expose useful CII status information.

The plugin must not become a second indexing engine.

It must communicate with the standalone CII application through a supported interface.

Do not rely on undocumented OpenCode internals.

The MCP server must remain fully operational without the plugin.

---

# 16. AI Development Workflow

This section defines the intended behaviour when MiMo uses CII.

## 16.1 Before Development

When a user requests a coding task:

1. Identify the requested functionality.
2. Check CII status.
3. Search relevant symbols.
4. Identify existing classes and methods.
5. Identify relevant source files.
6. Retrieve the actual implementations.
7. Determine whether the requested functionality already exists.
8. Plan the smallest appropriate implementation.

The LLM should not automatically retrieve the entire project index.

It should retrieve only relevant structural information.

## 16.2 During Development

While implementing:

- Respect existing class boundaries.
- Respect namespaces.
- Reuse existing utilities.
- Avoid duplicate methods.
- Avoid unnecessary file creation.
- Preserve existing APIs unless modification is required.
- Keep changes focused on the requested task.

If new functionality belongs in an existing class, extend that class rather than creating another equivalent class.

## 16.3 After Development

When implementation is complete:

1. Identify changed source files.
2. Trigger incremental indexing.
3. Validate the changed files.
4. Run the relevant test suite.
5. Check for duplicate declarations.
6. Confirm that the generated index is current.
7. Report the integrity result.

## 16.4 Development Completion Report

The LLM should produce a concise report:

```text
CII DEVELOPMENT REPORT

Task: Audio device initialisation

Files modified: 2
Files created: 0

Classes modified: 1
Methods added: 2
Methods modified: 1

Duplicate symbols: None detected

Index status: HEALTHY
Validation: PASSED
Tests: PASSED

Development integrity: VERIFIED
```

Never report VERIFIED if any required validation step was skipped or failed.

---

# 17. Performance Requirements

CII must remain lightweight.

## 17.1 Performance Objectives

Initial engineering targets:

| Operation | Target |
|---|---|
| Database status | Under 100 ms |
| Single-file symbol lookup | Under 100 ms |
| Symbol search | Under 250 ms |
| Incremental scan | Proportional to changed files |
| Full scan | Scales with project size |
| Markdown export | Proportional to indexed symbols |

These are engineering targets, not guaranteed performance claims.

## 17.2 Resource Management

- Avoid loading entire projects into memory.
- Process files incrementally.
- Use efficient database queries.
- Cache parser instances where practical.
- Debounce filesystem events.
- Support background scanning.
- Avoid excessive filesystem polling.
- Do not repeatedly regenerate unchanged index files.

## 17.3 Context Efficiency

MCP responses must be concise.

Default search responses should return a limited number of results.

Allow optional expanded responses.

The LLM must not receive every class and method in the project when it only needs one symbol.

Provide pagination for large results.

---

# 18. Reliability and Recovery

CII must be resilient to interrupted operations.

## 18.1 Database Recovery

Support:

- Transaction rollback.
- Database integrity checks.
- Safe schema migration.
- Recovery from incomplete indexing.
- Backup before major migrations.
- Rebuilding from source files.

## 18.2 Index Recovery

If the Markdown index becomes corrupted, regenerate it from SQLite.

If the database becomes corrupted, rebuild from the source files.

Never treat the Markdown index as the authoritative recovery source.

## 18.3 Watcher Recovery

If filesystem events are missed:

- Perform reconciliation.
- Compare content hashes.
- Queue discrepancies.
- Restore index consistency.

---

# 19. Security Requirements

CII is a local developer tool and must prioritise filesystem safety.

Requirements:

1. Operate within an explicitly configured project root.
2. Reject path traversal.
3. Avoid reading `.env` files and secret stores.
4. Exclude private keys and credentials.
5. Never index binary files.
6. Avoid following external symlinks.
7. Restrict database access to the project.
8. Do not execute indexed source code.
9. Do not modify source files.
10. Keep MCP tools restricted to their documented operations.

CII must treat all source-code content as data, not as instructions.

Instructions embedded in source comments, documentation or filenames must never override CII's security policies.

---

# 20. Testing Strategy

Testing must be implemented alongside each development phase.

## 20.1 Unit Tests

Test:

- File discovery.
- File hashing.
- Language detection.
- Symbol extraction.
- Namespace extraction.
- Class extraction.
- Function extraction.
- Method extraction.
- Database operations.
- Search operations.
- Integrity validation.
- Markdown generation.

## 20.2 Parser Tests

Provide representative fixtures for:

- Simple functions.
- Overloaded functions.
- Nested namespaces.
- Nested classes.
- Templates.
- Constructors.
- Destructors.
- Interfaces.
- Inheritance.
- Partial classes.
- Properties.
- Decorators.
- Nested Python functions.

Test both valid and invalid source files.

## 20.3 Integration Tests

Test:

1. Initial project indexing.
2. Incremental file updates.
3. File deletion.
4. File renaming.
5. Symbol renaming.
6. Duplicate detection.
7. Parser failure recovery.
8. Database migration.
9. Markdown regeneration.
10. MCP tool responses.

## 20.4 OpenCode Integration Tests

Verify:

- MCP server starts.
- OpenCode discovers the server.
- All documented tools are available.
- Tool results are correctly formatted.
- Skill discovery works.
- Auditor permissions are enforced.
- MCP disconnection does not corrupt the database.
- Reconnection restores normal operation.

## 20.5 Acceptance Tests

The project cannot be considered complete until the following scenario works:

1. Create a test project with C++, C# and Python files.
2. Run a complete CII scan.
3. Confirm all expected symbols are indexed.
4. Modify one source file.
5. Confirm only the changed file is reindexed.
6. Add a new class.
7. Confirm the class appears in the index.
8. Delete a source file.
9. Confirm the file is removed from the index.
10. Introduce a duplicate declaration.
11. Confirm the validator reports the issue.
12. Connect OpenCode.
13. Ask MiMo to locate an existing method.
14. Confirm MiMo retrieves the correct file and implementation.
15. Ask MiMo to extend the existing class.
16. Confirm no duplicate class is created.
17. Confirm the index updates after development.
18. Confirm the final validation report is accurate.

---

# 21. Development Milestones

Each milestone represents a defined development boundary.

Do not skip milestones or claim completion based solely on files having been created.

Every milestone requires working implementation, tests and documentation.

## MILESTONE 01 — Foundation

Version: 0.1.0

Objectives:

- Initialise Python project.
- Create repository structure.
- Configure dependencies.
- Establish configuration management.
- Implement logging.
- Define core data models.
- Implement CLI entry point.
- Establish pytest infrastructure.

Deliverables:

- Working Python package.
- Project configuration.
- Basic CLI.
- Initial tests.
- README.

Acceptance:

CII installs and executes successfully.

## MILESTONE 02 — Database

Version: 0.2.0

Objectives:

- Implement SQLite integration.
- Create database schema.
- Implement repositories.
- Implement transactions.
- Implement schema versioning.
- Implement project registration.
- Implement database health checks.

Acceptance:

CII can create, open, query and validate a persistent project database.

## MILESTONE 03 — Scanner

Version: 0.3.0

Objectives:

- Implement project discovery.
- Implement file filtering.
- Implement file hashing.
- Implement change detection.
- Implement file classification.
- Implement exclusion configuration.

Acceptance:

CII can discover eligible project files and identify file changes accurately.

## MILESTONE 04 — Initial Parser Engine

Version: 0.4.0

Objectives:

- Implement parser interface.
- Integrate Tree-sitter.
- Implement C++ extraction.
- Implement C extraction.
- Implement C# extraction.
- Implement Python AST extraction.
- Extract namespaces, classes, functions and methods.
- Implement symbol fingerprints.

Acceptance:

CII accurately indexes representative C++, C, C# and Python projects.

## MILESTONE 05 — Structural Indexer

Version: 0.5.0

Objectives:

- Implement symbol extraction pipeline.
- Implement symbol registration.
- Implement symbol relationships.
- Implement symbol counts.
- Implement namespace organisation.
- Implement Markdown exporter.
- Implement CODEBASE_INDEX.md.

Acceptance:

A complete structural index can be generated from the database.

## MILESTONE 06 — Integrity Engine

Version: 0.6.0

Objectives:

- Implement index validation.
- Implement file reconciliation.
- Implement stale record detection.
- Implement deletion detection.
- Implement rename detection.
- Implement duplicate detection.
- Implement integrity reporting.

Acceptance:

CII can identify discrepancies between the filesystem and the database without corrupting existing records.

## MILESTONE 07 — Incremental Monitoring

Version: 0.7.0

Objectives:

- Implement filesystem watcher.
- Implement event queue.
- Implement debounce logic.
- Implement incremental rescanning.
- Implement recovery from missed events.
- Implement startup reconciliation.

Acceptance:

Changes to project files are reflected in the structural index automatically.

## MILESTONE 08 — Search and Retrieval

Version: 0.8.0

Objectives:

- Implement symbol search.
- Implement file search.
- Implement namespace search.
- Implement class and method lookup.
- Implement relationship queries.
- Implement pagination.
- Implement concise search results.

Acceptance:

CII can locate symbols accurately without loading the entire index.

## MILESTONE 09 — MCP Server

Version: 0.9.0

Objectives:

- Integrate official Python MCP SDK.
- Implement all nine MCP tools.
- Implement MCP resources.
- Implement input validation.
- Implement error handling.
- Implement project-root security.
- Implement stdio transport.

Acceptance:

An external MCP client can connect and use every documented CII operation.

## MILESTONE 10 — OpenCode Integration

Version: 0.10.0

Objectives:

- Create OpenCode skill.
- Create AGENTS.md integration instructions.
- Create codebase-auditor subagent.
- Generate OpenCode v2 configuration example.
- Verify local MCP registration.
- Verify tool discovery.
- Test MiMo development workflow.

Acceptance:

OpenCode can use CII to discover existing code before development.

## MILESTONE 11 — Automation and Plugin

Version: 0.11.0

Objectives:

- Implement optional OpenCode plugin.
- Integrate supported lifecycle hooks.
- Coordinate index refresh operations.
- Provide contextual integrity reminders.
- Implement plugin failure handling.

Acceptance:

CII continues to work independently of the plugin, while the plugin improves the development workflow.

## MILESTONE 12 — Reliability and Release

Version: 1.0.0

Objectives:

- Complete automated tests.
- Complete integration tests.
- Verify database recovery.
- Verify parser failure recovery.
- Review security boundaries.
- Benchmark large projects.
- Complete documentation.
- Verify installation on Linux and Windows.
- Produce release package.

Acceptance:

CII is independently installable, operational and reusable across multiple software projects.

---

# 22. Future Development

The following features are outside the initial release scope.

They must not delay version 1.0.

## 22.1 Semantic Code Intelligence

Potential capabilities:

- Call graph analysis.
- Dependency mapping.
- Inheritance trees.
- Interface implementation mapping.
- Cross-project symbol references.
- Unused symbol detection.
- API surface tracking.

## 22.2 Documentation Intelligence

Potential capabilities:

- Link source symbols to documentation.
- Identify undocumented public methods.
- Identify stale API documentation.
- Map documentation pages to implementation files.

## 22.3 Multi-Project Intelligence

Potential capabilities:

- Index multiple repositories.
- Shared component discovery.
- Cross-project dependency analysis.
- Reusable library identification.
- Global developer index.

## 22.4 Advanced AI Integration

Potential capabilities:

- Development history summaries.
- Architecture retrieval.
- Change impact analysis.
- Symbol-level change explanations.
- Context-aware task preparation.
- Development session handover.

These features must remain optional extensions.

The initial product is a deterministic structural indexing and integrity system.

---

# 23. Engineering Rules for the Implementing Agent

These requirements apply throughout development.

## 23.1 Implementation Discipline

- Implement one milestone at a time.
- Do not create placeholder implementations and declare them complete.
- Do not substitute mocked behaviour for working functionality in production code.
- Do not silently skip failed tests.
- Do not invent parser capabilities.
- Do not duplicate existing modules.
- Do not create unnecessary abstractions.
- Keep modules focused.
- Use type annotations.
- Document public interfaces.
- Follow consistent naming conventions.
- Handle errors explicitly.

## 23.2 Existing Codebase Inspection

Before modifying an existing file:

1. Inspect the file.
2. Identify its existing classes and functions.
3. Check relevant indexed symbols.
4. Understand its responsibilities.
5. Preserve existing functionality unless modification is required.

## 23.3 Index Integrity

The database and index exporter are the authoritative source of structural records.

The LLM must never directly fabricate index entries.

Any index changes must originate from successful parsing and database operations.

## 23.4 Testing Discipline

After each milestone:

1. Run unit tests.
2. Run relevant integration tests.
3. Run static checks.
4. Verify the acceptance criteria.
5. Update documentation.
6. Update the project changelog.
7. Record the completed milestone.

## 23.5 Git Discipline

Use Git commits as milestone boundaries.

Suggested commit messages:

```text
CII: M01 - Project Foundation
CII: M02 - SQLite Database
CII: M03 - Filesystem Scanner
CII: M04 - Parser Engine
CII: M05 - Structural Indexer
CII: M06 - Integrity Engine
CII: M07 - Incremental Monitoring
CII: M08 - Search and Retrieval
CII: M09 - MCP Server
CII: M10 - OpenCode Integration
CII: M11 - Automation Plugin
CII: M12 - Version 1.0 Release
```

Do not create commits that falsely indicate incomplete work is finished.

Do not push to a remote repository without explicit authorisation.

---

# 24. Definition of Done

CII version 1.0 is complete when:

- The application installs independently.
- A project can be registered.
- Source files can be discovered.
- C++, C, C# and Python can be indexed.
- Structural information is persisted in SQLite.
- Markdown indexes are generated.
- Incremental scanning works.
- File changes are detected.
- Index discrepancies are detected.
- Duplicate symbols can be identified.
- MCP tools work.
- OpenCode v2 connects successfully.
- MiMo can retrieve structural information.
- The auditor can inspect integrity.
- Source files remain untouched by CII.
- Recovery procedures work.
- Automated tests pass.
- Documentation is complete.

The final result must be a functional application, not merely a collection of architectural modules.

---

# 25. Final Product Vision

CII is intended to become a permanent structural intelligence layer for AI-assisted software development.

Its primary responsibility is to ensure that coding agents have an accurate understanding of what already exists before they create anything new.

The architecture deliberately separates:

**Development intelligence:** What the LLM is currently working on.

**Structural intelligence:** What the project actually contains.

The structural index persists independently of the LLM's conversation, session and context compaction.

This allows the coding agent to work with a large project without repeatedly loading its entire source tree or relying on conversational memory.

The system must be deterministic, verifiable, language-independent and reusable.

**Final architectural principle:**

The LLM decides what to build. CII establishes what already exists. The source code remains the ultimate authority.

---

# 26. Development Progress

Maintained by the implementing agent. Milestones are marked complete only after
their acceptance criteria have been executed and passed.

| Milestone | Version | Status | Evidence |
|---|---|---|---|
| M01 — Foundation | 0.1.0 | **COMPLETE** (2026-11-07) | Clean-venv install + `cii --version`/`init`/`config` executed; 74 unit tests pass; ruff clean |
| M02 — Database | 0.2.0 | **COMPLETE** (2026-11-07) | Create/open/query/validate executed on a persistent DB (clean-venv); 110 tests pass; ruff clean |
| M03 — Scanner | 0.3.0 | **COMPLETE** (2026-11-07) | Discovery + change detection executed end-to-end (add/modify/rename/delete, exclusion, binary/generated skip); 154 tests pass; ruff clean |
| M04 — Parser Engine | 0.4.0 | **COMPLETE** (2026-11-07) | Representative C++, C, C#, Python projects extracted accurately (clean-venv run verified); 198 tests pass; ruff clean |
| M05 — Structural Indexer | 0.5.0 | **COMPLETE** (2026-11-07) | Complete structural index generated from DB on multi-language project (clean-venv run verified); 224 tests pass; ruff clean |
| M06 — Integrity Engine | 0.6.0 | **COMPLETE** (2026-11-07) | Discrepancies identified (unindexed/missing/changed/renamed/duplicates) with records provably uncorrupted (clean-venv run verified); 256 tests pass; ruff clean |
| M07 — Incremental Monitoring | 0.7.0 | **COMPLETE** (2026-11-07) | Live watcher reflected concurrent add+delete automatically (clean-venv run verified); 281 tests pass incl. live inotify test; ruff clean |
| M08 — Search and Retrieval | 0.8.0 | **COMPLETE** (2026-11-07) | §11.2 example reproduced (3 implementations located, paginated, clean-venv); 301 tests pass; ruff clean |
| M09 — MCP Server | 0.9.0 | **COMPLETE** (2026-11-07) | External MCP client connected via stdio and used all 9 tools + 5 resources (clean-venv run verified); 328 tests pass; ruff clean |
| M10 — OpenCode Integration | 0.10.0 | **COMPLETE** (2026-11-07) | Live OpenCode v2.2.5: server connected, tools discovered, MiMo workflow executed end-to-end (skill → status → scan → search → source); 337 tests pass; ruff clean |
| M11 — Automation Plugin | 0.11.0 | **COMPLETE** (2026-11-07) | Live plugin: cii_status tool + injected reminders verified; failure handling verified; MCP independence retained; 343 tests pass; ruff clean |
| M12 — Reliability and Release | 1.0.0 | **COMPLETE** (2026-11-07) | §20.5 acceptance (18 steps) + auditor + recovery + benchmarks + wheel install verified on Linux; Windows install NOT RUN (no host — item 17); 351 tests pass; ruff clean |

## 26.1 Resolved specification ambiguities

Decisions taken where the specification left implementation details open:

1. **LICENSE**: not specified in PLAN.md — resolved 2026-11-07 by the project
   owner: **MIT** (LICENSE file, `pyproject.toml` SPDX field).
2. **`Namespaces` table semantics**: modelled as per-file namespace
   *declarations* (matching its field list); namespace identity across files is
   derived at query time (decision applied in M02).
3. **`index_scan` tool semantics**: executes the scan synchronously and returns
   the ScanHistory identifier plus final status (applied in M09).
4. **Clang/Roslyn analyzers** (`cpp/clang_analyzer.py`, `csharp/roslyn_analyzer.py`)
   and `core/events.py`: listed in the repository structure but not required by
   any milestone acceptance criterion — implemented only when a milestone needs
   them. v1.0 scope is Tree-sitter/AST extraction (§8.2 "when needed").
5. **`Files.scan_status` values**: `pending`, `indexed`, `failed`, `unsupported`.
6. **Header language ambiguity** (`.h`): defaults to `cpp`, configurable via
   `[languages].extensions`.
7. **`cii init` and VCS**: never edits user files (e.g. `.gitignore`); prints
   recommended entries instead.
8. **Configuration defaults source**: built-in Pydantic defaults are
   authoritative; `config/default.toml` is a reference copy enforced in sync by
   `tests/unit/test_default_config_sync.py`. Project overrides live in
   `.cii/config.toml` and are deep-merged per key.
9. **Default max file size**: 2 MiB (`scan.max_file_size_bytes`), configurable.
10. **M04 acceptance scope**: "accurately indexes" is satisfied at extraction
    level (parser output); persistent DB indexing is the M05 indexer's
    acceptance.
11. **Symbol model scope**: fields, enum members and global variables are not
    extracted (not in §5.1/§8.2 categories); `SymbolType` retains `field`/
    `enum_member` for future use. Python modules are represented by file
    records (no fabricated module symbol). C# `record` declarations map to
    `SymbolType.record`, counted as classes in statistics.
12. **Parser failure records** (§8.4): persisted via `files.scan_status` +
    `parser_version` and detailed `ParseIssue` entries (path, parser, reason,
    version, timestamp) surfaced through logs and reports; the schema stays as
    specified in §6.2.
13. **Duplicate-detection policy** (§10.4) and status precedence (§10.2):
    header/source pairs, overloads and C# partial classes are legitimate;
    identical definitions in multiple sources = ERROR; conflicting type shapes
    = WARNING; Python duplicates are compared within files only (file-local
    FQNs). Integrity status precedence: ERROR > INCOMPLETE > STALE > WARNING >
    HEALTHY (FAILED when validation itself cannot complete).
14. **Namespace attribution in search results** (§11.3): derived from the
    file's namespace declarations as the longest fully qualified prefix of the
    symbol name — the `symbols` table keeps exactly the §6.2 field set.
15. **MCP tool error policy** (§12.3): CII failures return structured
    `{"error": {type, message}}` payloads instead of crashing the session;
    unexpected failures are logged with traceback and surfaced as `internal`
    errors. `index_scan` executes synchronously (decision 3). The server uses
    the official SDK v2 (`MCPServer`); tool handlers run on worker threads and
    database access is serialised by a reentrant lock.
16. **Plugin scope** (§15.5): the plugin uses only documented V2 hooks and
    reaches CII through the CLI; it is never a second indexing engine. Plugin
    command dispatch (`/cii-audit`) relies on OpenCode's TUI command facility —
    registration and executor are tested, headless dispatch is not observable
    via `opencode run`.
17. **Windows verification** (§3.2, §21 M12): Windows installation and
    execution are **NOT RUN** — no Windows host was available during
    development. The implementation is platform-neutral by construction
    (pathlib, os.scandir, stdlib sqlite3, cross-platform watchfiles and
    tree-sitter wheels), but a Windows run of `scripts/verify_installation.py`
    and the test suite remains outstanding before Windows support can be
    claimed.

---

# END OF PLAN.md

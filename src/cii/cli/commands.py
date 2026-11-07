"""CII command-line interface.

The CLI operates independently of OpenCode (PLAN.md §13). Milestone 01 shipped
the entry point and foundation commands; Milestone 02 adds database creation,
project registration and index status. Scan, search and the remaining commands
arrive with their subsystems in later milestones.
"""

from pathlib import Path
from typing import Annotated

import typer

from cii import INDEX_VERSION, __version__
from cii.application import Application
from cii.cli.output import render_config, to_json
from cii.core.configuration import (
    CiiConfig,
    config_hash,
    load_config,
    project_config_path,
    save_project_config,
)
from cii.core.exceptions import CiiError
from cii.database.database import DATABASE_FILE_NAME, Database
from cii.database.repositories import FileRepository, ProjectRepository, SymbolRepository
from cii.integrity.validator import Validator
from cii.mcp.server import serve
from cii.mcp.tools import index_statistics
from cii.monitoring.watcher import ProjectWatcher
from cii.search.symbol_search import file_structure, search_symbols
from cii.utilities.logging import setup_logging
from cii.utilities.paths import cii_data_dir, resolve_project_root

app = typer.Typer(
    name="cii",
    help="Codebase Integrity & Intelligence — structural index for AI coding agents.",
    no_args_is_help=True,
)

_ROOT_OPTION = Annotated[
    Path,
    typer.Option("--root", help="Project root directory (default: current directory)."),
]
_JSON_OPTION = Annotated[
    bool,
    typer.Option("--json", help="Emit machine-readable JSON output."),
]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"cii {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the CII version and exit.",
        ),
    ] = False,
) -> None:
    """Codebase Integrity & Intelligence (CII)."""


@app.command("init")
def init_command(
    root: _ROOT_OPTION = Path("."),
    as_json: _JSON_OPTION = False,
) -> None:
    """Initialise CII in a project: create .cii/, write config, create the database.

    Existing configuration is preserved; the command is idempotent.
    """
    try:
        project_root = resolve_project_root(root)
        data_dir = cii_data_dir(project_root)
        cache_dir = data_dir / "cache"
        logs_dir = data_dir / "logs"
        cache_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        config = load_config(project_root)
        setup_logging(level=config.logging.level, console=not as_json, log_dir=logs_dir)

        config_path = project_config_path(project_root)
        config_created = not config_path.exists()
        if config_created:
            save_project_config(CiiConfig.defaults(), project_root)

        with Database.open(project_root) as database:
            project = ProjectRepository(database.connection).register(
                project_name=config.project.name or project_root.name,
                project_root=str(project_root),
                index_version=INDEX_VERSION,
                configuration_hash=config_hash(config),
            )
            health = database.health_check()

        result = {
            "project_root": str(project_root),
            "data_dir": str(data_dir),
            "config": str(config_path),
            "config_created": config_created,
            "database": str(data_dir / DATABASE_FILE_NAME),
            "project_id": project.project_id,
            "database_healthy": health.ok,
        }
        if as_json:
            typer.echo(to_json(result))
            return
        typer.echo(f"CII initialised in {project_root}")
        typer.echo(f"  data directory: {data_dir}")
        typer.echo(f"  configuration:  {config_path}"
                   + (" (created)" if config_created else " (preserved)"))
        typer.echo(f"  database:       {data_dir / DATABASE_FILE_NAME}"
                   + (" (healthy)" if health.ok else " (UNHEALTHY)"))
        typer.echo("")
        typer.echo("Recommended .gitignore entry (this command never edits your files):")
        typer.echo("  .cii/")
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("status")
def status_command(
    root: _ROOT_OPTION = Path("."),
    as_json: _JSON_OPTION = False,
) -> None:
    """Display index health and structural counts."""
    try:
        project_root = resolve_project_root(root)
        db_path = cii_data_dir(project_root) / DATABASE_FILE_NAME
        if not db_path.is_file():
            typer.secho(
                f"error: CII is not initialised in {project_root} (run 'cii init')",
                fg="red",
                err=True,
            )
            raise typer.Exit(code=1)

        with Database.open(project_root) as database:
            project = ProjectRepository(database.connection).get_by_root(str(project_root))
            if project is None:
                typer.secho(
                    "error: project not registered (run 'cii init')",
                    fg="red",
                    err=True,
                )
                raise typer.Exit(code=1)
            health = database.health_check()
            files = FileRepository(database.connection).list_all(project.project_id)
            symbol_count = SymbolRepository(database.connection).count_for_project(
                project.project_id
            )
            status_counts: dict[str, int] = {}
            for file_row in files:
                status_counts[file_row.scan_status] = status_counts.get(file_row.scan_status, 0) + 1

        result = {
            "project_name": project.project_name,
            "project_root": project.project_root,
            "index_version": project.index_version,
            "database_healthy": health.ok,
            "schema_version": health.schema_version,
            "integrity_check": health.integrity_check,
            "indexed_files": len(files),
            "files_by_status": status_counts,
            "indexed_symbols": symbol_count,
            "last_scan": project.last_scan,
        }
        if as_json:
            typer.echo(to_json(result))
            return
        typer.echo(f"Project:      {project.project_name}")
        typer.echo(f"Root:         {project.project_root}")
        typer.echo(f"Index:        v{project.index_version}"
                   + ("" if health.ok else "  (database UNHEALTHY)"))
        typer.echo(f"Database:     {db_path}")
        typer.echo(f"Schema:       v{health.schema_version} ({health.integrity_check})")
        typer.echo(f"Files:        {len(files)} indexed")
        for status, count in sorted(status_counts.items()):
            typer.echo(f"  {status}: {count}")
        typer.echo(f"Symbols:      {symbol_count}")
        typer.echo(f"Last scan:    {project.last_scan or 'never'}")
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("scan")
def scan_command(
    root: _ROOT_OPTION = Path("."),
    full: Annotated[
        bool,
        typer.Option("--full", help="Re-hash every file instead of trusting size/mtime."),
    ] = False,
    as_json: _JSON_OPTION = False,
) -> None:
    """Scan the project, index changed files, and refresh the Markdown index."""
    try:
        project_root = resolve_project_root(root)
        db_path = cii_data_dir(project_root) / DATABASE_FILE_NAME
        if not db_path.is_file():
            typer.secho(
                f"error: CII is not initialised in {project_root} (run 'cii init')",
                fg="red",
                err=True,
            )
            raise typer.Exit(code=1)
        with Application.open(project_root, configure_logging=True) as application:
            outcome = application.scan(full=full)

        changes = outcome.scan.changes
        index = outcome.index
        payload = {
            "scan_id": outcome.scan.scan_id,
            "mode": "full" if full else "incremental",
            "added": len(changes.added),
            "modified": len(changes.modified),
            "deleted": len(changes.deleted),
            "renamed": len(changes.renamed),
            "unchanged": changes.unchanged_count,
            "hashed_files": outcome.scan.hashed_files,
            "hash_skips": outcome.scan.hash_skips,
            "files_indexed": index.files_indexed,
            "files_failed": index.files_failed,
            "symbols_added": index.symbols_added,
            "symbols_updated": index.symbols_updated,
            "symbols_removed": index.symbols_removed,
            "relationships_unresolved": index.relationships_unresolved,
            "exported": outcome.exported,
            "skipped": outcome.scan.discovery.model_dump(),
        }
        if as_json:
            typer.echo(to_json(payload))
            return
        typer.echo(f"Scan #{outcome.scan.scan_id} ({payload['mode']}) complete")
        typer.echo(f"  added:     {payload['added']}")
        typer.echo(f"  modified:  {payload['modified']}")
        typer.echo(f"  deleted:   {payload['deleted']}")
        typer.echo(f"  renamed:   {payload['renamed']}")
        typer.echo(f"  unchanged: {payload['unchanged']}")
        typer.echo(
            f"  indexed:   {index.files_indexed} file(s), "
            f"+{index.symbols_added} ~{index.symbols_updated} -{index.symbols_removed} symbols"
        )
        if index.files_failed:
            typer.echo(f"  FAILED:    {index.files_failed} file(s) (previous index retained)")
        skipped = outcome.scan.discovery
        typer.echo(
            "  skipped:   "
            f"{skipped.unsupported_extension} unsupported, {skipped.too_large} too large, "
            f"{skipped.binary} binary, {skipped.generated} generated, "
            f"{skipped.symlink_skipped} symlinked"
        )
        for path in outcome.exported:
            typer.echo(f"  exported:  {path}")
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("export")
def export_command(
    root: _ROOT_OPTION = Path("."),
    as_json: _JSON_OPTION = False,
) -> None:
    """Regenerate CODEBASE_INDEX.md from the database."""
    try:
        project_root = resolve_project_root(root)
        db_path = cii_data_dir(project_root) / DATABASE_FILE_NAME
        if not db_path.is_file():
            typer.secho(
                f"error: CII is not initialised in {project_root} (run 'cii init')",
                fg="red",
                err=True,
            )
            raise typer.Exit(code=1)
        with Application.open(project_root) as application:
            written = application.export()
        if as_json:
            typer.echo(to_json({"exported": written}))
            return
        if written:
            for path in written:
                typer.echo(f"exported: {path}")
        else:
            typer.echo("index already up to date")
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("validate")
def validate_command(
    root: _ROOT_OPTION = Path("."),
    full: Annotated[
        bool,
        typer.Option("--full", help="Re-parse files and compare symbols with the index."),
    ] = False,
    as_json: _JSON_OPTION = False,
) -> None:
    """Validate index integrity against the filesystem (read-only)."""
    try:
        project_root = resolve_project_root(root)
        db_path = cii_data_dir(project_root) / DATABASE_FILE_NAME
        if not db_path.is_file():
            typer.secho(
                f"error: CII is not initialised in {project_root} (run 'cii init')",
                fg="red",
                err=True,
            )
            raise typer.Exit(code=1)
        with Application.open(project_root) as application:
            summary = Validator(
                project_root, application.config, application.database
            ).validate(full_scan=full)

        payload = {
            "status": summary.status.value,
            "errors": summary.errors,
            "warnings": summary.warnings,
            "files_checked": summary.files_checked,
            "full_scan": summary.full_scan,
            "findings": [finding.model_dump(mode="json") for finding in summary.findings],
        }
        if as_json:
            typer.echo(to_json(payload))
            return
        typer.echo(f"Integrity: {summary.status.value.upper()}")
        typer.echo(f"Files checked: {summary.files_checked}")
        typer.echo(f"Errors: {summary.errors}  Warnings: {summary.warnings}")
        for finding in summary.findings:
            location = f" [{finding.file_path}]" if finding.file_path else ""
            typer.echo(f"  {finding.severity.value.upper()} {finding.code}{location}")
            typer.echo(f"    {finding.message}")
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("search")
def search_command(
    query: Annotated[str, typer.Argument(help="Symbol name or fragment to locate.")],
    root: _ROOT_OPTION = Path("."),
    symbol_type: Annotated[
        str | None,
        typer.Option("--type", help="Filter by symbol type (class, method, …)."),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", help="Filter by language (cpp, csharp, …)."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum results.")] = 20,
    offset: Annotated[int, typer.Option("--offset", help="Skip the first N results.")] = 0,
    expanded: Annotated[
        bool,
        typer.Option("--expanded", help="Include signatures, lines and freshness."),
    ] = False,
    as_json: _JSON_OPTION = False,
) -> None:
    """Search indexed symbols without loading the whole index."""
    try:
        project_root = resolve_project_root(root)
        with Application.open(project_root) as application:
            project = ProjectRepository(application.database.connection).get_by_root(
                str(project_root)
            )
            if project is None:
                typer.secho("error: project not registered (run 'cii init')", fg="red",
                            err=True)
                raise typer.Exit(code=1)
            page = search_symbols(
                application.database,
                project.project_id,
                query,
                symbol_type=symbol_type,
                language=language,
                limit=limit,
                offset=offset,
                expanded=expanded,
            )
        if as_json:
            typer.echo(to_json(page.model_dump(mode="json")))
            return
        typer.echo(f"RESULTS: {page.total} (showing {len(page.results)})")
        for hit in page.results:
            typer.echo("")
            typer.echo(hit.file_path)
            typer.echo(f"    {hit.symbol_type}: {hit.fully_qualified_name}")
            if hit.parent:
                typer.echo(f"    parent: {hit.parent}")
            if hit.namespace:
                typer.echo(f"    namespace: {hit.namespace}")
            if expanded:
                if hit.signature:
                    typer.echo(f"    signature: {hit.signature}")
                typer.echo(f"    lines: {hit.start_line}-{hit.end_line}")
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("file")
def file_command(
    path: Annotated[str, typer.Argument(help="Project-relative file path.")],
    root: _ROOT_OPTION = Path("."),
    as_json: _JSON_OPTION = False,
) -> None:
    """Display a file's structural index."""
    try:
        project_root = resolve_project_root(root)
        with Application.open(project_root) as application:
            project = ProjectRepository(application.database.connection).get_by_root(
                str(project_root)
            )
            if project is None:
                typer.secho("error: project not registered (run 'cii init')", fg="red",
                            err=True)
                raise typer.Exit(code=1)
            structure = file_structure(application.database, project.project_id, path)
        if structure is None:
            typer.secho(f"error: file not indexed: {path}", fg="red", err=True)
            raise typer.Exit(code=1)
        if as_json:
            typer.echo(to_json(structure.model_dump(mode="json")))
            return
        typer.echo(f"FILE: {structure.file_path}")
        typer.echo("")
        typer.echo(f"LANGUAGE: {structure.language}")
        typer.echo("")
        counts = structure.counts
        typer.echo(f"NAMESPACES: {counts.namespaces}")
        typer.echo(f"CLASSES: {counts.classes}")
        typer.echo(f"FUNCTIONS: {counts.functions}")
        typer.echo(f"METHODS: {counts.methods}")
        if structure.namespaces:
            typer.echo("")
            typer.echo("NAMESPACE:")
            for name in structure.namespaces:
                typer.echo(f"    {name}")
        methods: dict[str, list[str]] = {}
        for symbol in structure.symbols:
            if symbol.symbol_type in ("method", "constructor", "destructor"):
                methods.setdefault(symbol.parent or "<global>", []).append(symbol.name)
        if methods:
            typer.echo("")
            typer.echo("METHODS:")
            for parent in sorted(methods):
                typer.echo(f"    {parent}:")
                for name in methods[parent]:
                    typer.echo(f"        {name}")
        functions = [s for s in structure.symbols if s.symbol_type == "function"]
        if functions:
            typer.echo("")
            typer.echo("FUNCTIONS:")
            for symbol in functions:
                typer.echo(f"    {symbol.name}")
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("watch")
def watch_command(
    root: _ROOT_OPTION = Path("."),
    max_seconds: Annotated[
        float | None,
        typer.Option("--max-seconds", help="Stop after N seconds (default: run until Ctrl+C)."),
    ] = None,
    as_json: _JSON_OPTION = False,
) -> None:
    """Watch the project and keep the index current automatically."""
    try:
        project_root = resolve_project_root(root)
        db_path = cii_data_dir(project_root) / DATABASE_FILE_NAME
        if not db_path.is_file():
            typer.secho(
                f"error: CII is not initialised in {project_root} (run 'cii init')",
                fg="red",
                err=True,
            )
            raise typer.Exit(code=1)
        with Application.open(project_root, configure_logging=True) as application:
            watcher = ProjectWatcher(application, application.config)
            typer.echo(f"Watching {project_root} (Ctrl+C to stop)")
            try:
                summary = watcher.run(max_seconds=max_seconds)
            except KeyboardInterrupt:
                typer.echo("stopped")
                raise typer.Exit(code=0) from None
        payload = summary.model_dump(mode="json")
        if as_json:
            typer.echo(to_json(payload))
            return
        typer.echo(
            f"done: {summary.scans_triggered} scan(s), "
            f"{summary.batches_processed} event batch(es), "
            f"{summary.reconciliations} reconciliation(s)"
        )
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("rebuild")
def rebuild_command(
    root: _ROOT_OPTION = Path("."),
    as_json: _JSON_OPTION = False,
) -> None:
    """Rebuild the project index from scratch (previous DB is backed up)."""
    try:
        project_root = resolve_project_root(root)
        db_path = cii_data_dir(project_root) / DATABASE_FILE_NAME
        if not db_path.is_file():
            typer.secho(
                f"error: CII is not initialised in {project_root} (run 'cii init')",
                fg="red",
                err=True,
            )
            raise typer.Exit(code=1)
        with Application.open(project_root, configure_logging=True) as application:
            outcome = application.rebuild()
        payload = {
            "scan_id": outcome.scan.scan_id,
            "backup_path": outcome.backup_path,
            "files_indexed": outcome.index.files_indexed,
            "symbols_added": outcome.index.symbols_added,
            "exported": outcome.exported,
        }
        if as_json:
            typer.echo(to_json(payload))
            return
        typer.echo(f"Rebuild complete (scan #{outcome.scan.scan_id})")
        typer.echo(f"  files indexed:   {outcome.index.files_indexed}")
        typer.echo(f"  symbols added:   {outcome.index.symbols_added}")
        typer.echo(f"  backup:          {outcome.backup_path}")
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("statistics")
def statistics_command(
    root: _ROOT_OPTION = Path("."),
    as_json: _JSON_OPTION = False,
) -> None:
    """Display project structural statistics."""
    try:
        project_root = resolve_project_root(root)
        db_path = cii_data_dir(project_root) / DATABASE_FILE_NAME
        if not db_path.is_file():
            typer.secho(
                f"error: CII is not initialised in {project_root} (run 'cii init')",
                fg="red",
                err=True,
            )
            raise typer.Exit(code=1)
        with Application.open(project_root) as application:
            stats = index_statistics(application)
        if as_json:
            typer.echo(to_json(stats.model_dump(mode="json")))
            return
        typer.echo(f"Files:   {stats.total_files} ({', '.join(
            f'{language}: {count}' for language, count in sorted(stats.files_by_language.items())
        )})")
        typer.echo(f"Symbols: {stats.total_symbols}")
        for symbol_type, count in sorted(stats.symbols_by_type.items()):
            typer.echo(f"  {symbol_type}: {count}")
        typer.echo(f"Namespaces: {stats.namespaces}")
        typer.echo(f"Parser failures: {stats.parser_failures}")
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("mcp")
def mcp_command(
    root: _ROOT_OPTION = Path("."),
) -> None:
    """Start the CII MCP server on stdio transport."""
    try:
        project_root = resolve_project_root(root)
        db_path = cii_data_dir(project_root) / DATABASE_FILE_NAME
        if not db_path.is_file():
            typer.secho(
                f"error: CII is not initialised in {project_root} (run 'cii init')",
                fg="red",
                err=True,
            )
            raise typer.Exit(code=1)
        serve(project_root)
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error


@app.command("config")
def config_command(
    root: _ROOT_OPTION = Path("."),
    as_json: _JSON_OPTION = False,
) -> None:
    """Show the effective configuration for a project."""
    try:
        project_root = resolve_project_root(root)
        config = load_config(project_root)
        if as_json:
            typer.echo(to_json(config.model_dump(mode="json")))
            return
        typer.echo(f"Project root: {project_root}")
        typer.echo(f"Config file:  {project_config_path(project_root)}")
        typer.echo("")
        for line in render_config(config.model_dump(mode="python")):
            typer.echo(line)
    except CiiError as error:
        typer.secho(f"error: {error}", fg="red", err=True)
        raise typer.Exit(code=1) from error

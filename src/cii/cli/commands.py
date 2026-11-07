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
from cii.scanner.scanner import Scanner
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
    """Scan the project and update the file index (incremental by default)."""
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
        config = load_config(project_root)
        setup_logging(
            level=config.logging.level,
            console=not as_json,
            log_dir=cii_data_dir(project_root) / "logs",
        )
        with Database.open(project_root) as database:
            result = Scanner(project_root, config, database).scan(full=full)

        changes = result.changes
        payload = {
            "scan_id": result.scan_id,
            "mode": "full" if full else "incremental",
            "added": len(changes.added),
            "modified": len(changes.modified),
            "deleted": len(changes.deleted),
            "renamed": len(changes.renamed),
            "unchanged": changes.unchanged_count,
            "hashed_files": result.hashed_files,
            "hash_skips": result.hash_skips,
            "skipped": result.discovery.model_dump(),
        }
        if as_json:
            typer.echo(to_json(payload))
            return
        typer.echo(f"Scan #{result.scan_id} ({payload['mode']}) complete")
        typer.echo(f"  added:     {payload['added']}")
        typer.echo(f"  modified:  {payload['modified']}")
        typer.echo(f"  deleted:   {payload['deleted']}")
        typer.echo(f"  renamed:   {payload['renamed']}")
        typer.echo(f"  unchanged: {payload['unchanged']}")
        skipped = result.discovery
        typer.echo(
            "  skipped:   "
            f"{skipped.unsupported_extension} unsupported, {skipped.too_large} too large, "
            f"{skipped.binary} binary, {skipped.generated} generated, "
            f"{skipped.symlink_skipped} symlinked"
        )
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

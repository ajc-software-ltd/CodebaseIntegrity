"""CII command-line interface.

The CLI operates independently of OpenCode (PLAN.md §13). Milestone 01 ships
the entry point plus the foundation commands; scan, status, search and the
remaining commands arrive with their subsystems in later milestones.
"""

from pathlib import Path
from typing import Annotated

import typer

from cii import __version__
from cii.cli.output import render_config, to_json
from cii.core.configuration import (
    CiiConfig,
    load_config,
    project_config_path,
    save_project_config,
)
from cii.core.exceptions import CiiError
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
    """Initialise CII in a project: create .cii/ and write the default config.

    Existing configuration is preserved; the command is idempotent.
    """
    try:
        project_root = resolve_project_root(root)
        data_dir = cii_data_dir(project_root)
        cache_dir = data_dir / "cache"
        logs_dir = data_dir / "logs"
        cache_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        setup_logging(console=not as_json, log_dir=logs_dir)

        config_path = project_config_path(project_root)
        config_created = not config_path.exists()
        if config_created:
            save_project_config(CiiConfig.defaults(), project_root)

        result = {
            "project_root": str(project_root),
            "data_dir": str(data_dir),
            "config": str(config_path),
            "config_created": config_created,
        }
        if as_json:
            typer.echo(to_json(result))
            return
        typer.echo(f"CII initialised in {project_root}")
        typer.echo(f"  data directory: {data_dir}")
        typer.echo(f"  configuration:  {config_path}"
                   + (" (created)" if config_created else " (preserved)"))
        typer.echo("")
        typer.echo("Recommended .gitignore entry (this command never edits your files):")
        typer.echo("  .cii/")
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

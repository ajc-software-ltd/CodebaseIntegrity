"""MCP resources (PLAN.md §12.2).

Read-only views of current database information, served as JSON:

- ``cii://project/status``
- ``cii://project/index``
- ``cii://project/statistics``
- ``cii://project/languages``
- ``cii://project/configuration``
"""

import json

from cii.application import Application
from cii.database.repositories import FileRepository, SymbolRepository
from cii.mcp import tools as tool_impl
from cii.parsers.registry import default_registry


def _dump(payload) -> str:  # type: ignore[no-untyped-def]
    return json.dumps(payload, indent=2, sort_keys=True)


def status_resource(app: Application) -> str:
    return _dump(tool_impl.index_status(app).model_dump(mode="json"))


def index_resource(app: Application) -> str:
    project_id = tool_impl._project_id(app)
    files = FileRepository(app.database.connection).list_all(project_id)
    symbol_repo = SymbolRepository(app.database.connection)
    payload = {
        "files": [
            {
                "relative_path": file_row.relative_path,
                "language": file_row.language,
                "scan_status": file_row.scan_status,
                "symbols": [
                    {"name": row.symbol_name, "type": row.symbol_type,
                     "fully_qualified_name": row.fully_qualified_name}
                    for row in symbol_repo.list_by_file(int(file_row.file_id))
                ],
            }
            for file_row in files
        ]
    }
    return _dump(payload)


def statistics_resource(app: Application) -> str:
    return _dump(tool_impl.index_statistics(app).model_dump(mode="json"))


def languages_resource(app: Application) -> str:
    project_id = tool_impl._project_id(app)
    files = FileRepository(app.database.connection).list_all(project_id)
    counts: dict[str, int] = {}
    for file_row in files:
        counts[file_row.language] = counts.get(file_row.language, 0) + 1
    return _dump({
        "supported": [language.value for language in default_registry().languages()],
        "files_by_language": counts,
    })


def configuration_resource(app: Application) -> str:
    return _dump(app.config.model_dump(mode="json"))

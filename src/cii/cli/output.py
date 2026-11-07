"""Output helpers for the CII CLI.

Keeps human-readable rendering separate from command logic so commands stay
short and rendering is testable in isolation.
"""

import json
from typing import Any


def render_config(data: dict[str, Any], *, indent: str = "") -> list[str]:
    """Render a nested configuration mapping as aligned ``key = value`` lines."""
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{indent}[{key}]")
            lines.extend(render_config(value, indent=indent + "  "))
        elif isinstance(value, list):
            rendered = ", ".join(str(item) for item in value)
            lines.append(f"{indent}{key} = [{rendered}]")
        elif isinstance(value, bool):
            lines.append(f"{indent}{key} = {'true' if value else 'false'}")
        else:
            lines.append(f"{indent}{key} = {value}")
    return lines


def to_json(data: Any) -> str:
    """Serialise data as pretty-printed JSON for machine-readable output."""
    return json.dumps(data, indent=2, sort_keys=True)

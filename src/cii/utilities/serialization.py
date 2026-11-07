"""Minimal TOML serialisation for CII configuration files.

Reading TOML uses the standard library :mod:`tomllib`. Writing is handled here
because CII only ever writes its own configuration shape: nested tables with
string, integer, boolean, list-of-string, and string-map values. Keeping the
writer scoped to that shape avoids an extra dependency.
"""

import json
from typing import Any


def _format_string(value: str) -> str:
    # TOML basic strings share JSON's escape conventions for the characters
    # that appear in configuration values.
    return json.dumps(value)


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return _format_string(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML value type: {type(value).__name__}")


def _format_key(key: str) -> str:
    if key and all(ch.isalnum() or ch in "-_" for ch in key):
        return key
    return _format_string(key)


def _dump_table(data: dict[str, Any], prefix: str, lines: list[str]) -> None:
    scalars: dict[str, Any] = {}
    tables: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            tables[key] = value
        else:
            scalars[key] = value

    if prefix:
        lines.append(f"[{prefix}]")
    for key, value in scalars.items():
        lines.append(f"{_format_key(key)} = {_format_value(value)}")
    for key, value in tables.items():
        if lines and lines[-1] != "":
            lines.append("")
        _dump_table(value, f"{prefix}.{key}" if prefix else _format_key(key), lines)


def dump_toml(data: dict[str, Any]) -> str:
    """Serialise a nested mapping to TOML text.

    Supported value types: ``str``, ``int``, ``float``, ``bool``,
    ``list`` of scalars, and nested ``dict`` (becomes a TOML table).
    """
    if not isinstance(data, dict):
        raise TypeError("dump_toml expects a dict")
    lines: list[str] = []
    _dump_table(data, "", lines)
    return "\n".join(lines).rstrip() + "\n"

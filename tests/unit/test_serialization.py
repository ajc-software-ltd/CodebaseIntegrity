"""Tests for the scoped TOML writer."""

import tomllib

import pytest

from cii.utilities.serialization import dump_toml


def _round_trip(data: dict) -> dict:
    return tomllib.loads(dump_toml(data))


class TestDumpToml:
    def test_scalars_round_trip(self) -> None:
        data = {"name": "demo", "count": 3, "ratio": 1.5, "enabled": True, "disabled": False}
        assert _round_trip(data) == data

    def test_lists_round_trip(self) -> None:
        data = {"dirs": [".git", ".cii"], "empty": []}
        assert _round_trip(data) == data

    def test_nested_tables_round_trip(self) -> None:
        data = {"outer": {"inner": {"value": "x"}, "other": 1}}
        assert _round_trip(data) == data

    def test_quoted_keys_round_trip(self) -> None:
        data = {"languages": {"extensions": {".c": "c", ".cpp": "cpp"}}}
        assert _round_trip(data) == data

    def test_string_escapes_round_trip(self) -> None:
        data = {"text": 'quote " and \\ backslash'}
        assert _round_trip(data) == data

    def test_rejects_unsupported_types(self) -> None:
        with pytest.raises(TypeError):
            dump_toml({"bad": {1, 2, 3}})

    def test_rejects_non_dict(self) -> None:
        with pytest.raises(TypeError):
            dump_toml([1, 2, 3])  # type: ignore[arg-type]

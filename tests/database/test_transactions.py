"""Tests for savepoint-based transaction management."""

import sqlite3

import pytest

from cii.database.transactions import transaction


@pytest.fixture
def connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.execute("CREATE TABLE t (x INTEGER)")
    yield connection
    connection.close()


class TestTransaction:
    def test_commits_on_success(self, connection: sqlite3.Connection) -> None:
        with transaction(connection):
            connection.execute("INSERT INTO t VALUES (1)")
        assert connection.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1

    def test_rolls_back_on_error(self, connection: sqlite3.Connection) -> None:
        with pytest.raises(RuntimeError):
            with transaction(connection):
                connection.execute("INSERT INTO t VALUES (1)")
                raise RuntimeError("boom")
        assert connection.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0

    def test_nested_inner_rollback_keeps_outer(self, connection: sqlite3.Connection) -> None:
        with transaction(connection):
            connection.execute("INSERT INTO t VALUES (1)")
            with pytest.raises(RuntimeError):
                with transaction(connection):
                    connection.execute("INSERT INTO t VALUES (2)")
                    raise RuntimeError("inner failure")
            connection.execute("INSERT INTO t VALUES (3)")
        values = [row[0] for row in connection.execute("SELECT x FROM t ORDER BY x")]
        assert values == [1, 3]

    def test_outer_rollback_discards_inner_commit(self, connection: sqlite3.Connection) -> None:
        with pytest.raises(RuntimeError):
            with transaction(connection):
                with transaction(connection):
                    connection.execute("INSERT INTO t VALUES (1)")
                raise RuntimeError("outer failure")
        assert connection.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0

    def test_nested_full_success(self, connection: sqlite3.Connection) -> None:
        with transaction(connection):
            with transaction(connection):
                connection.execute("INSERT INTO t VALUES (1)")
            connection.execute("INSERT INTO t VALUES (2)")
        assert connection.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 2

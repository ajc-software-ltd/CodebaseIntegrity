"""Transaction management for database writes.

Connections are opened in autocommit mode (``isolation_level=None``), so
multi-statement writes run inside :func:`transaction`, which uses SQL
savepoints. Savepoints nest safely, so a repository method can guarantee its
own atomicity while a caller wraps a larger operation (for example a whole
scan) in one outer transaction. A failed update can never leave a partially
applied index behind (PLAN.md §6.3, §18.1).
"""

import itertools
from collections.abc import Iterator
from contextlib import contextmanager
from sqlite3 import Connection

_savepoint_counter = itertools.count(1)


@contextmanager
def transaction(connection: Connection) -> Iterator[Connection]:
    """Run a block atomically on ``connection`` (nesting-safe via savepoints).

    Commits (releases) on success, rolls back on any exception.
    """
    name = f"cii_sp_{next(_savepoint_counter)}"
    connection.execute(f"SAVEPOINT {name}")
    try:
        yield connection
        connection.execute(f"RELEASE SAVEPOINT {name}")
    except BaseException:
        connection.execute(f"ROLLBACK TO SAVEPOINT {name}")
        connection.execute(f"RELEASE SAVEPOINT {name}")
        raise

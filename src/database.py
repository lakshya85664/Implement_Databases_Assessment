
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


DEFAULT_ORDERS = [
    ("ORD-1001", "shipped", 1250.00),
    ("ORD-1002", "processing", 750.50),
    ("ORD-1003", "delivered", 2400.00),
]


class Database:
    """SQLite database wrapper with nested transaction support."""

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        self.database_path = str(database_path)
        self.connection = sqlite3.connect(
            self.database_path,
            timeout=5.0,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._transaction_depth = 0

        self.initialize()

    def initialize(self) -> None:
        """Create tables and insert initial order records."""
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    total_amount REAL NOT NULL
                        CHECK (total_amount >= 0)
                )
                """
            )

            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS refunds (
                    refund_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    amount REAL NOT NULL CHECK (amount > 0),
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN (
                            'pending_approval',
                            'approved',
                            'rejected'
                        )
                    ),
                    approval_id TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id)
                        REFERENCES orders(order_id)
                )
                """
            )

            self.connection.executemany(
                """
                INSERT OR IGNORE INTO orders (
                    order_id,
                    status,
                    total_amount
                ) VALUES (?, ?, ?)
                """,
                DEFAULT_ORDERS,
            )

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] = (),
    ) -> sqlite3.Cursor:
        """Execute a parameterized SQL statement."""
        return self.connection.execute(sql, parameters)

    def fetch_one(
        self,
        sql: str,
        parameters: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        """Fetch one row as a dictionary, or None if not found."""
        row = self.connection.execute(sql, parameters).fetchone()
        return dict(row) if row is not None else None

    def fetch_all(
        self,
        sql: str,
        parameters: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        """Fetch all matching rows as dictionaries."""
        rows = self.connection.execute(sql, parameters).fetchall()
        return [dict(row) for row in rows]

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """
        Provide transaction boundaries with nested savepoints.

        The outermost transaction commits or rolls back the connection.
        Nested transactions use savepoints and do not commit the outer
        transaction.
        """
        if self._transaction_depth == 0:
            self.connection.execute("BEGIN")
            savepoint = None
        else:
            savepoint = (
                f"nested_transaction_{self._transaction_depth}"
            )
            self.connection.execute(f"SAVEPOINT {savepoint}")

        self._transaction_depth += 1

        try:
            yield
        except BaseException:
            if savepoint is None:
                self.connection.rollback()
            else:
                self.connection.execute(
                    f"ROLLBACK TO SAVEPOINT {savepoint}"
                )
                self.connection.execute(
                    f"RELEASE SAVEPOINT {savepoint}"
                )
            raise
        else:
            if savepoint is None:
                self.connection.commit()
            else:
                self.connection.execute(
                    f"RELEASE SAVEPOINT {savepoint}"
                )
        finally:
            self._transaction_depth -= 1

    def close(self) -> None:
        """Close the database connection."""
        self.connection.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()

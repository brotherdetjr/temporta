from __future__ import annotations

import sqlite3
from sqlite3 import Connection


class Conn:
    """
    A thing wrapper around sqlite3.Connection class to be used in unit tests.
    """

    connection: Connection

    def __init__(self, path: str) -> None:
        self.connection = sqlite3.connect(path)

    def one(self, sql: str, *args) -> tuple[any]:
        return self.connection.execute(sql, args).fetchone()

    def all(self, sql: str, *args) -> list[tuple[any]]:
        return self.connection.execute(sql, args).fetchall()

    def close(self) -> None:
        self.connection.close()

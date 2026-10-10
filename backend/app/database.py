from __future__ import annotations

import json
import re
from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError


class ResultAdapter:
    def __init__(self, result):
        self.result = result

    def fetchone(self) -> dict[str, Any] | None:
        row = self.result.mappings().fetchone()
        return dict(row) if row else None

    def fetchall(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.result.mappings().fetchall()]


class ConnectionAdapter:
    """Small compatibility layer so domain SQL works on SQLite and PostgreSQL."""

    def __init__(self, connection: Connection):
        self.connection = connection

    @staticmethod
    def _prepare(sql: str, params: tuple[Any, ...]) -> tuple[str, dict[str, Any]]:
        # SQLite's INSERT OR IGNORE is represented portably with ON CONFLICT DO NOTHING.
        sql = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", sql, flags=re.I)
        if "INSERT OR IGNORE" not in sql.upper() and "ON CONFLICT" not in sql.upper():
            # The regex above has already removed the phrase, so detect the specific inserts by table.
            if "INSERT INTO recovery_actions" in sql or "INSERT INTO recovery_attributions" in sql:
                sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        bind: dict[str, Any] = {}
        for index in range(sql.count("?")):
            sql = sql.replace("?", f":p{index}", 1)
            bind[f"p{index}"] = params[index]
        return sql, bind

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> ResultAdapter:
        if not params and "?" not in sql:
            return ResultAdapter(self.connection.exec_driver_sql(sql))
        prepared, bind = self._prepare(sql, params)
        return ResultAdapter(self.connection.execute(text(prepared), bind))


class Database:
    def __init__(self, url: str):
        if url == ":memory:":
            url = "sqlite+pysqlite:///:memory:"
        elif url.startswith("sqlite:///"):
            url = url.replace("sqlite:///", "sqlite+pysqlite:///", 1)
        self.url = url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        self.initialize()

    @contextmanager
    def transaction(self) -> Iterator[ConnectionAdapter]:
        with self.engine.begin() as connection:
            yield ConnectionAdapter(connection)

    @contextmanager
    def connection(self) -> Iterator[ConnectionAdapter]:
        with self.engine.connect() as connection:
            yield ConnectionAdapter(connection)

    def initialize(self) -> None:
        # Alembic owns production schema creation. For tests/dev SQLite, create schema directly.
        if self.url.startswith("sqlite"):
            from .schema import create_schema
            create_schema(self.engine)

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return connection.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connection() as connection:
            return connection.execute(sql, params).fetchone()

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

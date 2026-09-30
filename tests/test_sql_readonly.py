"""Regressions for read-only SQLite access and SQL validation."""
import sqlite3

import pytest

from app.sql.sqlite_adapter import SQLiteAdapter
from app.sql.validators import validate_sql_query


def test_sqlite_adapter_allows_select_but_rejects_writes(tmp_path):
    db_path = tmp_path / "data.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO items(name) VALUES ('sample')")

    with SQLiteAdapter.connect(str(db_path)) as conn:
        assert conn.execute("SELECT name FROM items").fetchone()["name"] == "sample"
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO items(name) VALUES ('forbidden')")


def test_sql_validator_rejects_mutation():
    assert validate_sql_query("SELECT * FROM items")["valid"]
    for statement in ("DELETE FROM items", "DROP TABLE items", "UPDATE items SET name='x'"):
        assert not validate_sql_query(statement)["valid"]

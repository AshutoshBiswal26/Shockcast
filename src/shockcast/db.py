"""DuckDB connection, schema loading and migration (drift) check.

`db/schema.sql` is the single source of truth. Every statement in it is
`CREATE TABLE IF NOT EXISTS`, so applying it is idempotent. Because
`IF NOT EXISTS` never alters an existing table, `check_schema` compares the live
database against a fresh in-memory build of the schema and reports any drift.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

# src/shockcast/db.py -> repo root is two levels above the package directory.
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


@dataclass(frozen=True, order=True)
class ColumnSpec:
    name: str
    data_type: str
    nullable: bool
    default: str | None


@dataclass(frozen=True)
class TableSpec:
    columns: tuple[ColumnSpec, ...]
    primary_key: tuple[str, ...]


class SchemaMismatchError(RuntimeError):
    """Raised when the database does not match `db/schema.sql`."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Schema mismatch:\n  - " + "\n  - ".join(problems))


def read_schema_sql(schema_path: Path = DEFAULT_SCHEMA_PATH) -> str:
    return schema_path.read_text(encoding="utf-8")


def introspect(con: duckdb.DuckDBPyConnection) -> dict[str, TableSpec]:
    """Return column and primary-key specs for every table in the main schema."""
    cols = con.execute(
        """
        SELECT table_name, column_name, data_type, is_nullable = 'YES', column_default
        FROM information_schema.columns
        WHERE table_schema = 'main'
        ORDER BY table_name, ordinal_position
        """
    ).fetchall()
    pks = con.execute(
        """
        SELECT table_name, constraint_column_names
        FROM duckdb_constraints()
        WHERE schema_name = 'main' AND constraint_type = 'PRIMARY KEY'
        """
    ).fetchall()
    pk_map: dict[str, tuple[str, ...]] = {t: tuple(c) for t, c in pks}

    by_table: dict[str, list[ColumnSpec]] = {}
    for table, name, dtype, nullable, default in cols:
        by_table.setdefault(table, []).append(
            ColumnSpec(name, dtype, bool(nullable), None if default is None else str(default))
        )
    return {
        t: TableSpec(tuple(c), pk_map.get(t, ())) for t, c in by_table.items()
    }


def expected_schema(schema_sql: str) -> dict[str, TableSpec]:
    """Build the schema in a throwaway in-memory DB and introspect it."""
    with duckdb.connect(":memory:") as mem:
        mem.execute(schema_sql)
        return introspect(mem)


def check_schema(
    con: duckdb.DuckDBPyConnection, schema_path: Path = DEFAULT_SCHEMA_PATH
) -> list[str]:
    """Compare the live DB against `schema.sql`. Returns a list of problems (empty = OK).

    Extra tables in the DB are allowed; extra or changed columns in schema tables are not.
    """
    expected = expected_schema(read_schema_sql(schema_path))
    actual = introspect(con)
    problems: list[str] = []
    for table, exp in sorted(expected.items()):
        act = actual.get(table)
        if act is None:
            problems.append(f"missing table '{table}'")
            continue
        exp_cols = {c.name: c for c in exp.columns}
        act_cols = {c.name: c for c in act.columns}
        for name in exp_cols.keys() - act_cols.keys():
            problems.append(f"{table}: missing column '{name}'")
        for name in act_cols.keys() - exp_cols.keys():
            problems.append(f"{table}: unexpected column '{name}'")
        for name in exp_cols.keys() & act_cols.keys():
            e, a = exp_cols[name], act_cols[name]
            if e.data_type != a.data_type:
                problems.append(
                    f"{table}.{name}: type {a.data_type}, expected {e.data_type}"
                )
            if e.nullable != a.nullable:
                problems.append(
                    f"{table}.{name}: nullable={a.nullable}, expected {e.nullable}"
                )
            if e.default != a.default:
                problems.append(
                    f"{table}.{name}: default {a.default!r}, expected {e.default!r}"
                )
        if exp.primary_key != act.primary_key:
            problems.append(
                f"{table}: primary key {list(act.primary_key)}, "
                f"expected {list(exp.primary_key)}"
            )
    return problems


def connect(db_path: str | Path) -> duckdb.DuckDBPyConnection:
    """Open (creating parent dirs if needed) a DuckDB database file or ':memory:'."""
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def init_db(
    db_path: str | Path, schema_path: Path = DEFAULT_SCHEMA_PATH
) -> duckdb.DuckDBPyConnection:
    """Open the DB, apply `schema.sql` (idempotent) and verify there is no drift.

    Raises SchemaMismatchError if an existing table differs from the schema file.
    """
    con = connect(db_path)
    try:
        con.execute(read_schema_sql(schema_path))
        problems = check_schema(con, schema_path)
        if problems:
            raise SchemaMismatchError(problems)
    except Exception:
        con.close()
        raise
    log.info("Schema OK at %s", db_path)
    return con

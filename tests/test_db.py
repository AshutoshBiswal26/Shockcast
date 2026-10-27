from __future__ import annotations

from pathlib import Path

import pytest

from shockcast.db import (
    DEFAULT_SCHEMA_PATH,
    SchemaMismatchError,
    check_schema,
    connect,
    expected_schema,
    init_db,
    read_schema_sql,
)

EXPECTED_TABLES = {
    "series", "sales", "calendar", "exog_signals", "text_items", "event_cache", "events",
    "shocks", "regimes", "runs", "forecasts", "metrics", "alerts", "decision_results",
}  # fmt: skip


def test_schema_file_defines_all_tables() -> None:
    assert set(expected_schema(read_schema_sql())) == EXPECTED_TABLES
    assert DEFAULT_SCHEMA_PATH.name == "schema.sql"


def test_init_db_creates_tables_and_passes_check(tmp_path: Path) -> None:
    db = tmp_path / "sub" / "x.duckdb"
    with init_db(db) as con:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert tables == EXPECTED_TABLES
        assert check_schema(con) == []


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "x.duckdb"
    with init_db(db) as con:
        con.execute("INSERT INTO series VALUES ('s1', 'i', 'st', NULL, NULL, NULL)")
    with init_db(db) as con:  # second run must not drop or duplicate data
        assert con.execute("SELECT count(*) FROM series").fetchone() == (1,)


def test_check_detects_missing_table_and_column_drift(tmp_path: Path) -> None:
    db = tmp_path / "x.duckdb"
    with connect(db) as con:
        con.execute(read_schema_sql())
        con.execute("DROP TABLE decision_results")
        con.execute("ALTER TABLE calendar ADD COLUMN extra INTEGER")
        con.execute("ALTER TABLE calendar DROP COLUMN snap_wi")
        problems = check_schema(con)
    assert "missing table 'decision_results'" in problems
    assert "calendar: unexpected column 'extra'" in problems
    assert "calendar: missing column 'snap_wi'" in problems


def test_check_detects_type_and_pk_drift(tmp_path: Path) -> None:
    db = tmp_path / "x.duckdb"
    with connect(db) as con:
        # Pre-existing table with a drifted definition: IF NOT EXISTS will not fix it.
        con.execute("CREATE TABLE metrics (run_id VARCHAR, model VARCHAR, variant VARCHAR,"
                    " regime VARCHAR, metric VARCHAR, value FLOAT)")  # fmt: skip
    with pytest.raises(SchemaMismatchError) as exc:
        init_db(db)
    joined = "\n".join(exc.value.problems)
    assert "metrics.value: type FLOAT, expected DOUBLE" in joined
    assert "metrics: primary key" in joined
    assert "metrics.run_id: nullable=True, expected False" in joined

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from shockcast.cli import main
from shockcast.db import init_db
from shockcast.ingest.m5 import M5FormatError, load_m5, select_series_ids

from ..conftest import N_DAYS, write_m5


@pytest.fixture
def con(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    c = init_db(tmp_path / "t.duckdb")
    yield c
    c.close()


def _counts(con: duckdb.DuckDBPyConnection) -> tuple[int, int, int]:
    return tuple(
        con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ("series", "sales", "calendar")
    )


def test_load_full(con: duckdb.DuckDBPyConnection, m5_dir: Path) -> None:
    report = load_m5(con, m5_dir)
    assert (report.n_series, report.n_sales_rows, report.n_calendar_rows) == (4, 4 * N_DAYS, N_DAYS)
    assert _counts(con) == (4, 4 * N_DAYS, N_DAYS)
    assert con.execute(
        "SELECT * FROM series WHERE series_id = 'FOODS_1_001_CA_1'"
    ).fetchone() == ("FOODS_1_001_CA_1", "FOODS_1_001", "CA_1", "FOODS_1", "FOODS", "CA")


def test_sales_values_dates_and_prices(con: duckdb.DuckDBPyConnection, m5_dir: Path) -> None:
    load_m5(con, m5_dir)
    # FOODS_1_001_CA_1: s_idx=0, i_idx=0 -> units = day % 7; d_1 = 2011-01-29
    rows = con.execute(
        "SELECT ds, units, sell_price FROM sales WHERE series_id = 'FOODS_1_001_CA_1' ORDER BY ds"
    ).fetchall()
    assert rows[0] == (date(2011, 1, 29), 0.0, 1.5)
    assert rows[8] == (date(2011, 2, 6), 1.0, 1.75)  # day index 8 -> week 2 price
    # HOBBIES_1_002_TX_1 has no week-1 price -> NULL for first 7 days, priced after.
    nulls = con.execute(
        "SELECT count(*) FILTER (WHERE sell_price IS NULL), count(sell_price) FROM sales "
        "WHERE series_id = 'HOBBIES_1_002_TX_1'"
    ).fetchone()
    assert nulls == (7, 3)


def test_calendar_mapping(con: duckdb.DuckDBPyConnection, m5_dir: Path) -> None:
    load_m5(con, m5_dir)
    row = con.execute("SELECT * FROM calendar WHERE ds = DATE '2011-01-31'").fetchone()
    assert row == (
        date(2011, 1, 31), 3, 1, 2011, "SuperBowl|ValentinesDay", "Sporting|Cultural",
        False, False, False,
    )  # fmt: skip
    first = con.execute("SELECT event_name, snap_ca, snap_wi FROM calendar ORDER BY ds").fetchmany(2)
    assert first == [(None, True, False), (None, False, True)]


def test_rerun_is_idempotent(con: duckdb.DuckDBPyConnection, m5_dir: Path) -> None:
    load_m5(con, m5_dir)
    before = con.execute("SELECT * FROM sales ORDER BY ALL").fetchall()
    load_m5(con, m5_dir)
    assert _counts(con) == (4, 4 * N_DAYS, N_DAYS)
    assert con.execute("SELECT * FROM sales ORDER BY ALL").fetchall() == before


def test_rerun_updates_changed_values(
    con: duckdb.DuckDBPyConnection, m5_dir: Path, tmp_path: Path
) -> None:
    load_m5(con, m5_dir)
    changed = write_m5(tmp_path / "m5_v2", units_offset=3)
    load_m5(con, changed)
    assert _counts(con) == (4, 4 * N_DAYS, N_DAYS)
    units = con.execute(
        "SELECT units FROM sales WHERE series_id = 'FOODS_1_001_CA_1' AND ds = '2011-01-29'"
    ).fetchone()
    assert units == (3.0,)


def test_subsample_is_seeded_and_deterministic(
    con: duckdb.DuckDBPyConnection, m5_dir: Path
) -> None:
    f = m5_dir / "sales_train_evaluation.csv"
    a = select_series_ids(con, f, 2, seed=1)
    assert a == select_series_ids(con, f, 2, seed=1)
    assert len(a) == 2
    assert select_series_ids(con, f, 100, seed=1) == sorted(select_series_ids(con, f, None, 1))
    report = load_m5(con, m5_dir, subsample_series=2, seed=1)
    assert report.n_series == 2
    assert _counts(con) == (2, 2 * N_DAYS, N_DAYS)


def test_missing_file_and_columns(con: duckdb.DuckDBPyConnection, m5_dir: Path) -> None:
    (m5_dir / "sell_prices.csv").unlink()
    with pytest.raises(M5FormatError, match="sell_prices.csv"):
        load_m5(con, m5_dir)
    (m5_dir / "sell_prices.csv").write_text("store_id,item_id\nCA_1,X\n", encoding="utf-8")
    with pytest.raises(M5FormatError, match="missing columns"):
        load_m5(con, m5_dir)
    assert _counts(con) == (0, 0, 0)


def test_failure_rolls_back(con: duckdb.DuckDBPyConnection, m5_dir: Path) -> None:
    # Duplicate calendar day -> error after staging; nothing must be committed.
    cal = m5_dir / "calendar.csv"
    lines = cal.read_text(encoding="utf-8").splitlines()
    cal.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")
    with pytest.raises(M5FormatError, match="duplicate"):
        load_m5(con, m5_dir)
    assert _counts(con) == (0, 0, 0)


def test_cli_ingest_twice(tmp_path: Path, m5_dir: Path) -> None:
    db = tmp_path / "cli.duckdb"
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        f"seed: 7\ndata:\n  m5_path: '{m5_dir.as_posix()}'\n  db_path: '{db.as_posix()}'\n"
        "  subsample_series: 3\n",
        encoding="utf-8",
    )
    assert main(["ingest", "--config", str(cfg)]) == 0
    assert main(["ingest", "--config", str(cfg)]) == 0
    assert main(["check-db", "--config", str(cfg)]) == 0
    with duckdb.connect(str(db)) as c:
        assert _counts(c) == (3, 3 * N_DAYS, N_DAYS)

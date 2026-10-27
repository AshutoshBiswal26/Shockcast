"""M5 loader: sales (wide -> long), sell prices and calendar into DuckDB.

Expected files in `m5_dir` (Kaggle M5 Forecasting layout):
  - calendar.csv
  - sell_prices.csv
  - sales_train_evaluation.csv  (preferred) or sales_train_validation.csv

Mapping to `db/schema.sql`:
  - series.series_id = "<item_id>_<store_id>" (the M5 `id` minus its
    `_evaluation`/`_validation` suffix, so the key is stable across both files).
  - sales.ds comes from calendar `d -> date`; sales.sell_price is joined on
    (store_id, item_id, wm_yr_wk) and is NULL for weeks without a listed price.
  - calendar.event_name / event_type join event_*_1 and event_*_2 with '|'.

All writes are `INSERT ... ON CONFLICT DO UPDATE` inside one transaction,
so re-running the loader never duplicates rows (R1.4).
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

SALES_FILES = ("sales_train_evaluation.csv", "sales_train_validation.csv")
CALENDAR_FILE = "calendar.csv"
PRICES_FILE = "sell_prices.csv"

SALES_ID_COLUMNS = ("id", "item_id", "dept_id", "cat_id", "store_id", "state_id")
CALENDAR_COLUMNS = (
    "date", "wm_yr_wk", "wday", "month", "year", "d",
    "event_name_1", "event_type_1", "event_name_2", "event_type_2",
    "snap_CA", "snap_TX", "snap_WI",
)  # fmt: skip
PRICES_COLUMNS = ("store_id", "item_id", "wm_yr_wk", "sell_price")

_CALENDAR_TYPES = (
    "{'date': 'DATE', 'wm_yr_wk': 'INTEGER', 'wday': 'TINYINT', 'month': 'TINYINT',"
    " 'year': 'SMALLINT', 'd': 'VARCHAR', 'event_name_1': 'VARCHAR',"
    " 'event_type_1': 'VARCHAR', 'event_name_2': 'VARCHAR', 'event_type_2': 'VARCHAR',"
    " 'snap_CA': 'INTEGER', 'snap_TX': 'INTEGER', 'snap_WI': 'INTEGER'}"
)
_PRICES_TYPES = (
    "{'store_id': 'VARCHAR', 'item_id': 'VARCHAR', 'wm_yr_wk': 'INTEGER',"
    " 'sell_price': 'DOUBLE'}"
)
_SALES_ID_TYPES = "{" + ", ".join(f"'{c}': 'VARCHAR'" for c in SALES_ID_COLUMNS) + "}"
_DAY_COLS = "COLUMNS('^d_[0-9]+$')"


class M5FormatError(ValueError):
    """Raised when M5 input files are missing or malformed."""


@dataclass(frozen=True)
class M5IngestReport:
    sales_file: Path
    n_series: int
    n_sales_rows: int
    n_calendar_rows: int
    n_priced_rows: int


def _lit(path: Path) -> str:
    """Render a path as a safely quoted SQL string literal."""
    return "'" + path.resolve().as_posix().replace("'", "''") + "'"


def find_sales_file(m5_dir: Path) -> Path:
    for name in SALES_FILES:
        candidate = m5_dir / name
        if candidate.is_file():
            return candidate
    raise M5FormatError(f"No M5 sales file found in {m5_dir}; expected one of {SALES_FILES}")


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise M5FormatError(f"Missing M5 file: {path}")
    return path


def _require_columns(
    con: duckdb.DuckDBPyConnection, path: Path, required: tuple[str, ...]
) -> list[str]:
    rows = con.execute(f"DESCRIBE SELECT * FROM read_csv({_lit(path)}, header=true)").fetchall()
    present = [r[0] for r in rows]
    missing = [c for c in required if c not in present]
    if missing:
        raise M5FormatError(f"{path.name} is missing columns: {missing}")
    return present


def select_series_ids(
    con: duckdb.DuckDBPyConnection, sales_file: Path, n: int | None, seed: int
) -> list[str]:
    """Pick M5 `id`s to load: all of them, or a seeded random subset of size n.

    Ids are sorted before sampling so the subset depends only on (file contents, n, seed).
    """
    rows = con.execute(
        f"SELECT DISTINCT id FROM read_csv({_lit(sales_file)}, header=true,"
        f" types={_SALES_ID_TYPES}) ORDER BY id"
    ).fetchall()
    ids = [r[0] for r in rows]
    if n is None or n >= len(ids):
        if n is not None:
            log.warning("subsample_series=%d >= %d available; loading all", n, len(ids))
        return ids
    return sorted(random.Random(seed).sample(ids, n))


def load_m5(
    con: duckdb.DuckDBPyConnection,
    m5_dir: str | Path,
    subsample_series: int | None = None,
    seed: int = 42,
) -> M5IngestReport:
    """Load M5 calendar, series, sales and prices with idempotent upserts."""
    m5_dir = Path(m5_dir)
    sales_file = find_sales_file(m5_dir)
    calendar_file = _require_file(m5_dir / CALENDAR_FILE)
    prices_file = _require_file(m5_dir / PRICES_FILE)

    _require_columns(con, calendar_file, CALENDAR_COLUMNS)
    _require_columns(con, prices_file, PRICES_COLUMNS)
    sales_cols = _require_columns(con, sales_file, SALES_ID_COLUMNS)
    day_cols = [c for c in sales_cols if re.fullmatch(r"d_[0-9]+", c)]
    if not day_cols:
        raise M5FormatError(f"{sales_file.name} has no d_<n> day columns")

    ids = select_series_ids(con, sales_file, subsample_series, seed)
    log.info("Loading %d M5 series from %s", len(ids), sales_file.name)

    con.execute("BEGIN TRANSACTION")
    try:
        _stage(con, sales_file, calendar_file, prices_file, ids)
        cal_days = {r[0] for r in con.execute("SELECT d FROM _m5_cal").fetchall()}
        unmatched = [d for d in day_cols if d not in cal_days]
        if unmatched:
            log.warning("%d day columns have no calendar date; skipped", len(unmatched))
        _upsert_calendar(con)
        _upsert_series(con)
        n_sales, n_priced = _upsert_sales(con)
        n_cal = _count(con, "_m5_cal")
        n_series = _count(con, "_m5_wide")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        for t in ("_m5_ids", "_m5_cal", "_m5_wide", "_m5_prices"):
            con.execute(f"DROP TABLE IF EXISTS {t}")

    report = M5IngestReport(sales_file, n_series, n_sales, n_cal, n_priced)
    log.info("M5 ingest done: %s", report)
    return report


def _count(con: duckdb.DuckDBPyConnection, table: str) -> int:
    row = con.execute(f"SELECT count(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


def _stage(
    con: duckdb.DuckDBPyConnection,
    sales_file: Path,
    calendar_file: Path,
    prices_file: Path,
    ids: list[str],
) -> None:
    con.execute("CREATE OR REPLACE TEMP TABLE _m5_ids (id VARCHAR PRIMARY KEY)")
    con.executemany("INSERT INTO _m5_ids VALUES (?)", [(i,) for i in ids])
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _m5_cal AS
        SELECT * FROM read_csv({_lit(calendar_file)}, header=true, types={_CALENDAR_TYPES})
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _m5_wide AS
        SELECT s.* FROM read_csv({_lit(sales_file)}, header=true, types={_SALES_ID_TYPES}) s
        SEMI JOIN _m5_ids USING (id)
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _m5_prices AS
        SELECT p.* FROM read_csv({_lit(prices_file)}, header=true, types={_PRICES_TYPES}) p
        SEMI JOIN (SELECT DISTINCT item_id, store_id FROM _m5_wide) w
          ON p.item_id = w.item_id AND p.store_id = w.store_id
        """
    )
    dupes = con.execute(
        "SELECT count(*) FROM (SELECT d FROM _m5_cal GROUP BY d HAVING count(*) > 1)"
    ).fetchone()
    if dupes and dupes[0]:
        raise M5FormatError("calendar.csv has duplicate 'd' values")


def _upsert_calendar(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        INSERT INTO calendar
            (ds, wday, month, year, event_name, event_type, snap_ca, snap_tx, snap_wi)
        SELECT
            date, wday, month, year,
            NULLIF(concat_ws('|', event_name_1, event_name_2), ''),
            NULLIF(concat_ws('|', event_type_1, event_type_2), ''),
            snap_CA = 1, snap_TX = 1, snap_WI = 1
        FROM _m5_cal
        ON CONFLICT (ds) DO UPDATE SET
            wday = EXCLUDED.wday, month = EXCLUDED.month, year = EXCLUDED.year,
            event_name = EXCLUDED.event_name, event_type = EXCLUDED.event_type,
            snap_ca = EXCLUDED.snap_ca, snap_tx = EXCLUDED.snap_tx,
            snap_wi = EXCLUDED.snap_wi
        """
    )


def _upsert_series(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        INSERT INTO series (series_id, item_id, store_id, dept_id, cat_id, state_id)
        SELECT item_id || '_' || store_id, item_id, store_id, dept_id, cat_id, state_id
        FROM _m5_wide
        ON CONFLICT (series_id) DO UPDATE SET
            item_id = EXCLUDED.item_id, store_id = EXCLUDED.store_id,
            dept_id = EXCLUDED.dept_id, cat_id = EXCLUDED.cat_id,
            state_id = EXCLUDED.state_id
        """
    )


def _upsert_sales(con: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    """Melt day columns to long format and upsert. Returns (rows, rows with a price)."""
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE _m5_long AS
        SELECT
            u.item_id || '_' || u.store_id AS series_id,
            c.date AS ds,
            CAST(u.units AS DOUBLE) AS units,
            p.sell_price
        FROM (
            UNPIVOT (SELECT item_id, store_id, {_DAY_COLS} FROM _m5_wide)
            ON {_DAY_COLS} INTO NAME d VALUE units
        ) u
        JOIN _m5_cal c ON c.d = u.d
        LEFT JOIN _m5_prices p
          ON p.item_id = u.item_id AND p.store_id = u.store_id AND p.wm_yr_wk = c.wm_yr_wk
        """
    )
    try:
        con.execute(
            """
            INSERT INTO sales (series_id, ds, units, sell_price)
            SELECT series_id, ds, units, sell_price FROM _m5_long
            ON CONFLICT (series_id, ds) DO UPDATE SET
                units = EXCLUDED.units, sell_price = EXCLUDED.sell_price
            """
        )
        row = con.execute("SELECT count(*), count(sell_price) FROM _m5_long").fetchone()
        return (int(row[0]), int(row[1])) if row else (0, 0)
    finally:
        con.execute("DROP TABLE IF EXISTS _m5_long")

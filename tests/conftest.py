"""Shared fixtures: a tiny synthetic dataset in the real M5 file layout."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import pytest

N_DAYS = 10
START = date(2011, 1, 29)  # M5's real first day (a Saturday, wm_yr_wk 11101)
STORES = [("CA_1", "CA"), ("TX_1", "TX")]
ITEMS = [("FOODS_1_001", "FOODS_1", "FOODS"), ("HOBBIES_1_002", "HOBBIES_1", "HOBBIES")]


def _write(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def write_m5(root: Path, units_offset: int = 0) -> Path:
    """Write calendar.csv, sell_prices.csv and sales_train_evaluation.csv to root."""
    root.mkdir(parents=True, exist_ok=True)
    cal_rows: list[list[object]] = []
    for i in range(N_DAYS):
        d = START + timedelta(days=i)
        week = 11101 + i // 7
        ev1 = ("SuperBowl", "Sporting") if i == 2 else ("", "")
        ev2 = ("ValentinesDay", "Cultural") if i == 2 else ("", "")
        cal_rows.append(
            [d.isoformat(), week, d.strftime("%A"), (i % 7) + 1, d.month, d.year, f"d_{i + 1}",
             ev1[0], ev1[1], ev2[0], ev2[1], int(i % 3 == 0), 0, int(i == 1)]
        )  # fmt: skip
    _write(
        root / "calendar.csv",
        ["date", "wm_yr_wk", "weekday", "wday", "month", "year", "d", "event_name_1",
         "event_type_1", "event_name_2", "event_type_2", "snap_CA", "snap_TX", "snap_WI"],
        cal_rows,
    )  # fmt: skip

    price_rows: list[list[object]] = []
    sales_rows: list[list[object]] = []
    for s_idx, (store, state) in enumerate(STORES):
        for i_idx, (item, dept, cat) in enumerate(ITEMS):
            # Item 2 in store 2 has no price in week 1 -> NULL sell_price.
            for week in (11101, 11102):
                if not (s_idx == 1 and i_idx == 1 and week == 11101):
                    price_rows.append([store, item, week, 1.5 + i_idx + (week - 11101) * 0.25])
            units = [(s_idx * 10 + i_idx + day + units_offset) % 7 for day in range(N_DAYS)]
            sales_rows.append(
                [f"{item}_{store}_evaluation", item, dept, cat, store, state, *units]
            )
    _write(root / "sell_prices.csv", ["store_id", "item_id", "wm_yr_wk", "sell_price"], price_rows)
    _write(
        root / "sales_train_evaluation.csv",
        ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
        + [f"d_{i + 1}" for i in range(N_DAYS)],
        sales_rows,
    )
    return root


@pytest.fixture
def m5_dir(tmp_path: Path) -> Path:
    return write_m5(tmp_path / "m5")

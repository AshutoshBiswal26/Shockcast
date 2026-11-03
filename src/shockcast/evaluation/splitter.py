"""Rolling-origin train/test splits and a feature leakage guard (R2.1, R2.2).

Origins are anchored to the last date in the data: the latest origin is
`last_date - horizon`, so its test window ends exactly on `last_date`, and each
earlier origin steps back by `stride` days. Fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from shockcast.config import BacktestConfig


class LeakageError(ValueError):
    """Raised when a feature uses information from after the forecast origin."""


@dataclass(frozen=True)
class Split:
    origin: pd.Timestamp
    train: pd.DataFrame  # rows with ds <= origin
    test: pd.DataFrame  # rows with origin < ds <= origin + horizon


def rolling_origin_splits(
    sales: pd.DataFrame, cfg: BacktestConfig, ds_col: str = "ds"
) -> list[Split]:
    """Split `sales` into rolling-origin folds, returned in chronological order."""
    if sales.empty:
        raise ValueError("sales DataFrame is empty; cannot build rolling-origin splits")
    ds = pd.to_datetime(sales[ds_col])
    first, last = ds.min(), ds.max()
    horizon = pd.Timedelta(days=cfg.horizon)
    origins = [
        last - horizon - pd.Timedelta(days=k * cfg.stride) for k in reversed(range(cfg.n_origins))
    ]
    if origins[0] < first:
        needed = cfg.horizon + (cfg.n_origins - 1) * cfg.stride + 1
        available = (last - first).days + 1
        raise ValueError(
            f"Data too short for {cfg.n_origins} origins with horizon={cfg.horizon}, "
            f"stride={cfg.stride}: need at least {needed} days, have {available} "
            f"({first.date()} to {last.date()})"
        )
    return [
        Split(
            origin=origin,
            train=sales[ds <= origin],
            test=sales[(ds > origin) & (ds <= origin + horizon)],
        )
        for origin in origins
    ]


def check_no_leakage(features: pd.DataFrame, origin: pd.Timestamp, ts_col: str) -> None:
    """Raise LeakageError if any timestamp in `ts_col` is missing or after `origin`.

    A date-only origin compares as midnight, so anything stamped later on the
    origin day counts as leakage.
    """
    ts = pd.to_datetime(features[ts_col])
    origin = pd.Timestamp(origin)
    if ts.isna().any():
        raise LeakageError(f"{int(ts.isna().sum())} feature rows have no '{ts_col}' timestamp")
    leaky = ts > origin
    if leaky.any():
        raise LeakageError(
            f"{int(leaky.sum())} feature rows have '{ts_col}' after origin {origin}; "
            f"latest is {ts.max()}"
        )

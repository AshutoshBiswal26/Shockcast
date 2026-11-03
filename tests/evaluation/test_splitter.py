from __future__ import annotations

from itertools import pairwise

import pandas as pd
import pytest

from shockcast.config import BacktestConfig
from shockcast.evaluation.splitter import LeakageError, check_no_leakage, rolling_origin_splits

CFG = BacktestConfig(horizon=7, stride=5, n_origins=4)


def _sales(n_days: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2011-01-29", periods=n_days, freq="D")
    return pd.DataFrame(
        [
            {"series_id": sid, "ds": d, "units": float(i % 7)}
            for sid in ("A", "B")
            for i, d in enumerate(dates)
        ]
    )


def test_train_never_after_origin() -> None:
    for split in rolling_origin_splits(_sales(), CFG):
        assert not split.train.empty
        assert (split.train["ds"] <= split.origin).all()


def test_test_windows_disjoint_from_train_and_exact_horizon() -> None:
    for split in rolling_origin_splits(_sales(), CFG):
        assert set(split.test["ds"]).isdisjoint(set(split.train["ds"]))
        assert split.test["ds"].nunique() == CFG.horizon
        assert (split.test["ds"] > split.origin).all()
        assert (split.test["ds"] <= split.origin + pd.Timedelta(days=CFG.horizon)).all()


def test_origins_chronological_and_last_window_ends_at_last_date() -> None:
    sales = _sales()
    splits = rolling_origin_splits(sales, CFG)
    origins = [s.origin for s in splits]
    assert len(origins) == CFG.n_origins
    assert origins == sorted(origins)
    assert all(b - a == pd.Timedelta(days=CFG.stride) for a, b in pairwise(origins))
    assert splits[-1].test["ds"].max() == sales["ds"].max()


def test_leakage_guard() -> None:
    origin = pd.Timestamp("2011-02-10")
    clean = pd.DataFrame({"published_at": pd.date_range("2011-02-01", origin, freq="D")})
    check_no_leakage(clean, origin, ts_col="published_at")

    leaky = pd.concat(
        [clean, pd.DataFrame({"published_at": [origin + pd.Timedelta(hours=1)]})],
        ignore_index=True,
    )
    with pytest.raises(LeakageError, match="after origin"):
        check_no_leakage(leaky, origin, ts_col="published_at")


def test_data_too_short_raises() -> None:
    # Needs horizon + (n_origins - 1) * stride + 1 = 7 + 15 + 1 = 23 days.
    rolling_origin_splits(_sales(23), CFG)
    with pytest.raises(ValueError, match=r"Data too short .* need at least 23 days, have 22"):
        rolling_origin_splits(_sales(22), CFG)

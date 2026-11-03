from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from shockcast.config import BacktestConfig, ShockCastConfig, load_config


def test_defaults_populate_backtest_section() -> None:
    cfg = ShockCastConfig()
    assert cfg.seed == 42
    assert cfg.backtest.horizon == 28
    assert cfg.backtest.stride == 28
    assert cfg.backtest.n_origins == 8


def test_backtest_allows_extra_keys() -> None:
    bt = BacktestConfig.model_validate(
        {"horizon": 14, "quantiles": [0.1, 0.5, 0.9]}
    )
    assert bt.horizon == 14
    # extra="allow" keeps unknown keys accessible.
    assert bt.model_extra == {"quantiles": [0.1, 0.5, 0.9]}


@pytest.mark.parametrize("field", ["horizon", "stride", "n_origins"])
def test_backtest_rejects_non_positive_values(field: str) -> None:
    with pytest.raises(ValidationError):
        BacktestConfig.model_validate({field: 0})


def test_load_config_reads_backtest_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "cfg.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "seed": 7,
                "backtest": {"horizon": 7, "stride": 1, "n_origins": 3, "quantiles": [0.5]},
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.seed == 7
    assert cfg.backtest.horizon == 7
    assert cfg.backtest.stride == 1
    assert cfg.backtest.n_origins == 3
    assert cfg.backtest.model_extra == {"quantiles": [0.5]}


def test_load_config_empty_yaml_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.backtest.n_origins == 8


def test_shipped_default_config_validates() -> None:
    cfg = load_config(Path("configs/default.yaml"))
    assert cfg.backtest.horizon == 28
    assert cfg.backtest.model_extra["quantiles"] == [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]

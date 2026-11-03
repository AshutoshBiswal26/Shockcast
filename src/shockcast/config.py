"""Experiment configuration loaded from YAML and validated with Pydantic."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class DataConfig(BaseModel):
    """Data locations and subsampling options."""

    model_config = ConfigDict(extra="forbid")

    m5_path: Path = Path("data/raw/m5")
    db_path: Path = Path("data/shockcast.duckdb")
    # None means "load every series"; an int selects a seeded random subset.
    subsample_series: int | None = Field(default=None, ge=1)
    geographies: list[str] = Field(default_factory=lambda: ["CA", "TX", "WI"])


class BacktestConfig(BaseModel):
    """Rolling-origin backtest settings (R2.1). Other keys (e.g. quantiles) pass through."""

    model_config = ConfigDict(extra="allow")

    horizon: int = Field(default=28, ge=1)
    stride: int = Field(default=28, ge=1)
    n_origins: int = Field(default=8, ge=1)


class ShockCastConfig(BaseModel):
    """Top-level config. Sections owned by later tasks are accepted but not yet typed."""

    model_config = ConfigDict(extra="allow")

    seed: int = 42
    data: DataConfig = Field(default_factory=DataConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)


def load_config(path: str | Path) -> ShockCastConfig:
    """Load and validate a YAML config file."""
    with Path(path).open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return ShockCastConfig.model_validate(raw)

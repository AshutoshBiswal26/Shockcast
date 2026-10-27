# ShockCast
Early-warning demand forecasting with calibrated uncertainty and decision-cost evaluation.

## Quick start
```
uv sync
uv run python -m shockcast.cli ingest --config configs/default.yaml
uv run python -m shockcast.cli backtest --config configs/default.yaml
```

## Building with Kiro
Open this folder in Kiro. Steering files in `.kiro/steering/` load automatically.
Open the **Specs** panel, select `shockcast`, and run tasks from `tasks.md` one at a time.

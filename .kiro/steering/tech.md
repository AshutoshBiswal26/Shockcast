---
inclusion: always
---
# Technology Stack

- Language: Python 3.11, managed with `uv`
- Data: DuckDB + Parquet files under `data/` (no server needed)
- Forecasting: `statsforecast` (baselines), `lightgbm`, `chronos-forecasting` (foundation model), PyTorch
- Uncertainty: custom adaptive conformal inference (ACI) in `src/shockcast/conformal/`
- Change-point / regime: `ruptures`, custom Bayesian online change-point detection (BOCPD)
- NLP event extraction: pluggable LLM client (local Ollama or API) returning JSON validated by Pydantic
- API: FastAPI. Dashboard: Streamlit. Config: YAML + Pydantic settings
- Tests: pytest, hypothesis (property tests for conformal coverage)
- Lint/format: ruff. Types: mypy (strict on `src/shockcast/`)

## Common commands
- Install: `uv sync`
- Tests: `uv run pytest -q`
- Lint: `uv run ruff check . && uv run ruff format --check .`
- Types: `uv run mypy src/shockcast`
- Backtest: `uv run python -m shockcast.cli backtest --config configs/default.yaml`
- Dashboard: `uv run streamlit run src/shockcast/dashboard/app.py`

## Conventions
- Type hints everywhere; Pydantic models for all external data contracts.
- Seeds come from config; all experiments must be reproducible.
- Never commit raw datasets or API keys. Secrets via `.env` (gitignored).

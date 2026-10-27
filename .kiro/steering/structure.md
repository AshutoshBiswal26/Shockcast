---
inclusion: always
---
# Project Structure

```
shockcast/
├── .kiro/                  # steering, specs, hooks, settings
├── configs/default.yaml    # experiment configuration
├── db/schema.sql           # DuckDB schema (source of truth for tables)
├── data/                   # gitignored: raw/ interim/ processed/
├── src/shockcast/
│   ├── ingest/             # M5, Wikipedia, Trends, Open-Meteo, GDELT loaders
│   ├── events/             # LLM event extraction + schema validation
│   ├── features/           # lags, calendar, exogenous, event covariates
│   ├── models/             # baselines, lightgbm, chronos wrappers
│   ├── regime/             # BOCPD / HMM regime detection
│   ├── conformal/          # adaptive conformal prediction
│   ├── decision/           # newsvendor optimizer + inventory simulator
│   ├── evaluation/         # backtest harness, metrics, ablations
│   ├── api/                # FastAPI app
│   └── dashboard/          # Streamlit app
├── tests/                  # mirrors src/ layout
└── reports/                # generated figures and ablation tables
```

## Naming
- Modules: snake_case. Classes: PascalCase. One responsibility per module.
- Every model implements `shockcast.models.base.Forecaster` (fit / predict_quantiles).
- Tests named `test_<module>.py`.

## Spec generation rules (keep specs lean)
- Limit each requirement to at most 5 acceptance criteria, written in EARS form.
- design.md: no more than one architecture diagram; skip generic test plans.
- tasks.md: each task references the requirement IDs it satisfies.

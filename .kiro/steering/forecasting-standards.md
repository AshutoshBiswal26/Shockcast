---
inclusion: fileMatch
fileMatchPattern: "src/shockcast/{models,evaluation,conformal,features}/**/*.py"
---
# Forecasting Correctness Rules

- Backtests are rolling-origin only. Features at time t may use data <= t only.
  Any feature built from a rolling window must be shifted so it cannot see the target.
- Exogenous covariates must be lagged by their real publication delay.
- Report sMAPE, MASE, CRPS (or weighted quantile loss), interval coverage and width.
  Always split metrics into `normal` vs `shock` periods.
- Conformal intervals: report empirical coverage vs nominal, rolling over time.
- Compare every new model against seasonal-naive and LightGBM baselines.
- Add a leakage test for each new feature family.

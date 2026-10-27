# Implementation Plan

- [ ] 1. Project scaffolding
  - Create package layout, `pyproject.toml`, ruff/mypy/pytest config, `.gitignore`, `.env.example`
  - _Requirements: R1_

- [ ] 2. Database and ingestion
  - [ ] 2.1 Implement `db/schema.sql` loader and migration check
    - _Requirements: R1.1, R1.4_
  - [ ] 2.2 M5 loader (sales, prices, calendar) with idempotent upserts
    - _Requirements: R1.1, R1.4_
  - [ ] 2.3 Exogenous loaders: Open-Meteo, Wikipedia pageviews, Google Trends, GDELT, with `published_at`, retry and backoff
    - _Requirements: R1.2, R1.3_

- [ ] 3. Backtesting harness and metrics
  - [ ] 3.1 Rolling-origin splitter with leakage guard
    - _Requirements: R2.1, R2.2_
  - [ ] 3.2 Metrics: sMAPE, MASE, CRPS/WQL, coverage, width, regime-split reporting
    - _Requirements: R2.3_
  - [ ] 3.3 Reproducibility: seeding and golden-file test
    - _Requirements: R2.4_

- [ ] 4. Baseline forecasters
  - [ ] 4.1 `Forecaster` protocol and seasonal-naive, ETS
    - _Requirements: R3.1_
  - [ ] 4.2 LightGBM quantile model with lag/calendar features
    - _Requirements: R3.1, R3.3_
  - [ ] 4.3 Chronos wrapper (zero-shot), then fine-tune mode
    - _Requirements: R3.1, R3.2_

- [ ] 5. Shock labeling
  - [ ] 5.1 Robust seasonal-baseline deviation labeler
    - _Requirements: R4.1, R4.3_
  - [ ] 5.2 Synthetic shock injector with configurable shape and magnitude
    - _Requirements: R4.2_

- [ ] 6. Exogenous features
  - [ ] 6.1 Weather, attention and calendar covariates with publication-delay lagging and leakage tests
    - _Requirements: R1.2, R2.2_

- [ ] 7. LLM event extraction
  - [ ] 7.1 `EventRecord` schema, prompt v1, validation and retries
    - _Requirements: R5.1, R5.2_
  - [ ] 7.2 Output cache keyed by (model, prompt version, text hash)
    - _Requirements: R5.4_
  - [ ] 7.3 Aggregation into lagged per-day, per-geography covariates
    - _Requirements: R5.3_

- [ ] 8. Regime detection
  - [ ] 8.1 BOCPD on baseline residuals
    - _Requirements: R6.1_
  - [ ] 8.2 Regime state machine and `regimes` persistence
    - _Requirements: R6.1, R6.3_
  - [ ] 8.3 Regime-aware blending with validation-only weights
    - _Requirements: R6.2_

- [ ] 9. Adaptive conformal prediction
  - [ ] 9.1 ACI wrapper over any quantile forecaster
    - _Requirements: R7.1_
  - [ ] 9.2 Rolling coverage reporting, split by regime
    - _Requirements: R7.2_
  - [ ] 9.3 Hypothesis property test for stationary coverage
    - _Requirements: R7.3_

- [ ] 10. Early-warning alerts
  - [ ] 10.1 Alert rules over signal and event scores
    - _Requirements: R8.1_
  - [ ] 10.2 Matching alerts to shocks: lead time, precision, recall, false-alarm rate, per signal family
    - _Requirements: R8.2, R8.3_

- [ ] 11. Decision layer
  - [ ] 11.1 Newsvendor optimizer from quantile forecasts
    - _Requirements: R9.1_
  - [ ] 11.2 Inventory simulator and cost reporting vs seasonal-naive
    - _Requirements: R9.2, R9.3_

- [ ] 12. Ablations and reporting
  - [ ] 12.1 Ablation runner (series-only -> +calendar/weather -> +attention -> +events -> +regime -> +conformal)
    - _Requirements: R10.1_
  - [ ] 12.2 Bootstrap CIs, tables and figures into `reports/`
    - _Requirements: R10.2, R10.3_

- [ ] 13. API and dashboard
  - [ ] 13.1 FastAPI endpoints `/forecast/{series_id}` and `/alerts`
    - _Requirements: R11.1, R11.2_
  - [ ] 13.2 Streamlit app with intervals, alerts and explanation panel
    - _Requirements: R11.3_

- [ ] 14. Documentation
  - README with results, methodology, reproduction steps; short write-up of findings
    - _Requirements: R10.2_

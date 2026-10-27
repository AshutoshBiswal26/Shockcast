# Requirements Document

## Introduction
ShockCast forecasts retail demand with early warning of demand shocks, calibrated
prediction intervals, and decision-cost evaluation. Requirements use EARS syntax.

## Requirements

### R1: Data ingestion and storage
**User Story:** As a researcher, I want all sources loaded into one schema, so that experiments are reproducible.

#### Acceptance Criteria
1. WHEN the ingest command runs THEN the system SHALL load M5 sales, prices and calendar into DuckDB tables defined in `db/schema.sql`.
2. WHEN an exogenous source (weather, Wikipedia pageviews, Google Trends, GDELT) is ingested THEN the system SHALL store it with a timestamp and a `published_at` field.
3. IF a source request fails THEN the system SHALL retry with backoff and log the failure without aborting other sources.
4. WHEN ingest is re-run THEN the system SHALL be idempotent (no duplicate rows).

### R2: Backtesting harness
**User Story:** As a researcher, I want leak-free rolling-origin backtests, so that results are trustworthy.

#### Acceptance Criteria
1. WHEN a backtest runs THEN the system SHALL use rolling-origin splits only, with configurable horizon, stride and number of origins.
2. WHEN features are built THEN the system SHALL use only information available at the forecast origin.
3. WHEN a backtest finishes THEN the system SHALL write sMAPE, MASE, CRPS, coverage and width to the `metrics` table, split by `regime` (normal/shock).
4. WHEN the same config and seed are used THEN the system SHALL produce identical results.

### R3: Baseline and advanced forecasters
**User Story:** As a researcher, I want comparable models behind one interface, so that ablations are fair.

#### Acceptance Criteria
1. The system SHALL provide seasonal-naive, ETS, LightGBM and Chronos forecasters behind a common `Forecaster` interface returning quantiles.
2. WHEN Chronos is used THEN the system SHALL support both zero-shot and fine-tuned modes.
3. WHEN covariates are supplied THEN the system SHALL accept them for models that support exogenous inputs.

### R4: Shock labeling
**User Story:** As a researcher, I want ground-truth shocks, so that I can measure lead time and calibration in shock periods.

#### Acceptance Criteria
1. WHEN labeling runs THEN the system SHALL mark shock windows where the series deviates from a robust seasonal baseline beyond a configurable threshold.
2. WHEN synthetic shock injection is enabled THEN the system SHALL inject shocks of configurable magnitude, shape and duration and record them as labeled shocks with `source = synthetic`.
3. The system SHALL store labeled shocks in the `shocks` table.

### R5: LLM event extraction
**User Story:** As a researcher, I want unstructured text converted into structured event features, so that text can drive forecasts.

#### Acceptance Criteria
1. WHEN a text item is processed THEN the system SHALL return JSON validated against the `EventRecord` schema (type, direction, magnitude, geography, confidence).
2. IF the model output is invalid JSON or fails validation THEN the system SHALL retry up to a configurable limit and then record a null event with an error flag.
3. WHEN events are aggregated THEN the system SHALL produce per-day, per-geography covariates lagged by publication delay.
4. The system SHALL cache LLM outputs keyed by (model, prompt version, text hash).

### R6: Regime detection
**User Story:** As a researcher, I want to know the current regime, so that forecasters can be blended or switched.

#### Acceptance Criteria
1. WHEN a series is processed online THEN the system SHALL output a regime label (normal, pre_shock, shock, recovery) per timestep.
2. WHEN regime-aware blending is enabled THEN the system SHALL weight forecasters by regime using weights learned on validation origins only.
3. The system SHALL record regime outputs in the `regimes` table.

### R7: Calibrated uncertainty
**User Story:** As a decision maker, I want intervals that stay honest under shift, so that I can trust risk estimates.

#### Acceptance Criteria
1. WHEN forecasts are produced THEN the system SHALL wrap them with adaptive conformal prediction at configurable nominal levels.
2. WHEN evaluating THEN the system SHALL report rolling empirical coverage and mean interval width, separately for normal and shock periods.
3. WHEN a property test runs on stationary synthetic data THEN long-run coverage SHALL be within a configurable tolerance of nominal.

### R8: Early-warning lead time
**User Story:** As a researcher, I want lead time measured, so that I can show signals warn before the series moves.

#### Acceptance Criteria
1. WHEN an alert rule fires THEN the system SHALL record an alert with timestamp, series, score and triggering signals.
2. WHEN alerts are matched to labeled shocks THEN the system SHALL compute lead time in days, precision, recall and false-alarm rate.
3. The system SHALL report lead time per signal family (weather, attention, news events).

### R9: Decision layer
**User Story:** As a business stakeholder, I want forecasts judged by cost, so that value is clear.

#### Acceptance Criteria
1. WHEN quantile forecasts are given THEN the system SHALL compute newsvendor-optimal order quantities from configurable underage and overage costs.
2. WHEN a simulation runs THEN the system SHALL report stockout cost, holding cost and total cost per forecaster.
3. WHEN comparing forecasters THEN the system SHALL report cost savings relative to the seasonal-naive baseline, split by normal vs shock periods.

### R10: Ablation experiments and reporting
**User Story:** As a researcher, I want automated ablations, so that I can attribute gains to each signal.

#### Acceptance Criteria
1. WHEN the ablation command runs THEN the system SHALL evaluate: series-only, +calendar/weather, +attention, +LLM events, +regime blending, +conformal.
2. WHEN ablations finish THEN the system SHALL generate tables and figures in `reports/`.
3. The system SHALL include confidence intervals (bootstrap) on headline metric differences.

### R11: API and dashboard
**User Story:** As a user, I want to see forecasts and alerts, so that I can explore results.

#### Acceptance Criteria
1. WHEN `/forecast/{series_id}` is called THEN the API SHALL return quantile forecasts, interval bounds and current regime.
2. WHEN `/alerts` is called THEN the API SHALL return recent shock alerts with triggering events.
3. WHEN the dashboard loads THEN it SHALL show forecasts with shaded intervals, shock alerts and an explanation panel citing triggering events.

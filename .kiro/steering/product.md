---
inclusion: always
---
# Product: ShockCast

ShockCast is an early-warning demand forecaster. It detects demand shocks from
external signals (weather, attention, news, events) BEFORE they appear in the
sales series, forecasts through them with calibrated uncertainty, and evaluates
success by inventory decision cost, not only error metrics.

## Core questions the project must answer (every design choice serves these)
1. Do exogenous signals and LLM-extracted event features improve forecasts?
2. Do prediction intervals stay honest (covered) DURING shocks?
3. How many days of lead time do signals give before the series moves?
4. Does better forecasting reduce simulated inventory cost?

## Users
Primary: the author (portfolio / research-grade project). Secondary: readers of
the README and write-up who want reproducible results.

## Non-goals
- No live trading or real inventory integration.
- No hand-tuned per-series hacks; methods must generalize across series.
- No random train/test splits. Ever.

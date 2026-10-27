-- ShockCast DuckDB schema (source of truth)

CREATE TABLE IF NOT EXISTS series (
    series_id   VARCHAR PRIMARY KEY,
    item_id     VARCHAR NOT NULL,
    store_id    VARCHAR NOT NULL,
    dept_id     VARCHAR,
    cat_id      VARCHAR,
    state_id    VARCHAR
);

CREATE TABLE IF NOT EXISTS sales (
    series_id   VARCHAR NOT NULL REFERENCES series(series_id),
    ds          DATE    NOT NULL,
    units       DOUBLE  NOT NULL,
    sell_price  DOUBLE,
    PRIMARY KEY (series_id, ds)
);

CREATE TABLE IF NOT EXISTS calendar (
    ds          DATE PRIMARY KEY,
    wday        TINYINT,
    month       TINYINT,
    year        SMALLINT,
    event_name  VARCHAR,
    event_type  VARCHAR,
    snap_ca     BOOLEAN,
    snap_tx     BOOLEAN,
    snap_wi     BOOLEAN
);

-- Generic exogenous signals (weather, wikipedia, trends)
CREATE TABLE IF NOT EXISTS exog_signals (
    source        VARCHAR   NOT NULL,   -- weather | wikipedia | trends
    signal_name   VARCHAR   NOT NULL,
    geography     VARCHAR   NOT NULL DEFAULT 'global',
    ds            DATE      NOT NULL,
    value         DOUBLE    NOT NULL,
    published_at  TIMESTAMP NOT NULL,   -- when the value became knowable
    PRIMARY KEY (source, signal_name, geography, ds)
);

CREATE TABLE IF NOT EXISTS text_items (
    text_id       VARCHAR PRIMARY KEY,
    source        VARCHAR NOT NULL,     -- gdelt | reddit | news
    text          VARCHAR NOT NULL,
    geography     VARCHAR,
    published_at  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS event_cache (
    cache_key      VARCHAR PRIMARY KEY, -- hash(model, prompt_version, text_hash)
    model          VARCHAR NOT NULL,
    prompt_version VARCHAR NOT NULL,
    raw_response   VARCHAR NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS events (
    text_id      VARCHAR PRIMARY KEY REFERENCES text_items(text_id),
    event_type   VARCHAR NOT NULL,
    direction    VARCHAR NOT NULL,
    magnitude    VARCHAR NOT NULL,
    geography    VARCHAR,
    confidence   DOUBLE  NOT NULL,
    published_at TIMESTAMP NOT NULL,
    error        BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS shocks (
    shock_id    VARCHAR PRIMARY KEY,
    series_id   VARCHAR NOT NULL REFERENCES series(series_id),
    start_ds    DATE NOT NULL,
    end_ds      DATE NOT NULL,
    direction   VARCHAR NOT NULL,       -- up | down
    magnitude   DOUBLE NOT NULL,        -- relative deviation from baseline
    source      VARCHAR NOT NULL        -- detected | synthetic
);

CREATE TABLE IF NOT EXISTS regimes (
    run_id     VARCHAR NOT NULL,
    series_id  VARCHAR NOT NULL,
    ds         DATE    NOT NULL,
    regime     VARCHAR NOT NULL,        -- normal | pre_shock | shock | recovery
    score      DOUBLE,
    PRIMARY KEY (run_id, series_id, ds)
);

CREATE TABLE IF NOT EXISTS runs (
    run_id       VARCHAR PRIMARY KEY,
    config_json  VARCHAR NOT NULL,
    git_sha      VARCHAR,
    seed         INTEGER NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS forecasts (
    run_id       VARCHAR NOT NULL REFERENCES runs(run_id),
    model        VARCHAR NOT NULL,
    variant      VARCHAR NOT NULL,      -- ablation arm
    series_id    VARCHAR NOT NULL,
    origin_ds    DATE NOT NULL,
    ds           DATE NOT NULL,
    q05 DOUBLE, q10 DOUBLE, q25 DOUBLE, q50 DOUBLE,
    q75 DOUBLE, q90 DOUBLE, q95 DOUBLE,
    conf_lo      DOUBLE,                -- conformalized bounds
    conf_hi      DOUBLE,
    actual       DOUBLE,
    PRIMARY KEY (run_id, model, variant, series_id, origin_ds, ds)
);

CREATE TABLE IF NOT EXISTS metrics (
    run_id    VARCHAR NOT NULL REFERENCES runs(run_id),
    model     VARCHAR NOT NULL,
    variant   VARCHAR NOT NULL,
    regime    VARCHAR NOT NULL,         -- normal | shock | all
    metric    VARCHAR NOT NULL,         -- smape | mase | crps | coverage | width
    value     DOUBLE NOT NULL,
    PRIMARY KEY (run_id, model, variant, regime, metric)
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id     VARCHAR PRIMARY KEY,
    run_id       VARCHAR NOT NULL,
    series_id    VARCHAR NOT NULL,
    ts           TIMESTAMP NOT NULL,
    score        DOUBLE NOT NULL,
    signal_family VARCHAR NOT NULL,     -- weather | attention | news
    trigger_json VARCHAR,
    matched_shock_id VARCHAR,
    lead_days    DOUBLE
);

CREATE TABLE IF NOT EXISTS decision_results (
    run_id         VARCHAR NOT NULL,
    model          VARCHAR NOT NULL,
    variant        VARCHAR NOT NULL,
    regime         VARCHAR NOT NULL,
    stockout_cost  DOUBLE NOT NULL,
    holding_cost   DOUBLE NOT NULL,
    total_cost     DOUBLE NOT NULL,
    service_level  DOUBLE,
    PRIMARY KEY (run_id, model, variant, regime)
);

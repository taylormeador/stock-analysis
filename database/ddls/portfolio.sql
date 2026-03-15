CREATE TABLE IF NOT EXISTS portfolio_calculations (
    id                          SERIAL PRIMARY KEY,
    symbol                      VARCHAR(20)     NOT NULL,
    date                        DATE            NOT NULL,

    -- inputs
    trading_capital             NUMERIC(12, 2)  NOT NULL,
    volatility_target_pct       NUMERIC(6, 4)   NOT NULL,
    current_price               NUMERIC(12, 4)  NOT NULL,

    -- volatility chain
    ewma_vol                    NUMERIC(10, 6)  NOT NULL,
    block_value                 NUMERIC(12, 4)  NOT NULL,
    instrument_value_volatility NUMERIC(12, 4)  NOT NULL,

    -- vol targets
    annualized_cash_vol_target  NUMERIC(12, 2)  NOT NULL,
    daily_cash_vol_target       NUMERIC(12, 2)  NOT NULL,
    vol_scalar                  NUMERIC(12, 4)  NOT NULL,

    -- forecast
    combined_forecast           NUMERIC(10, 4)  NOT NULL,

    -- position sizing chain
    subsystem_position          NUMERIC(10, 4)  NOT NULL,
    instrument_weight           NUMERIC(8, 6)   NOT NULL,
    idm                         NUMERIC(6, 4)   NOT NULL,
    portfolio_position          NUMERIC(10, 4)  NOT NULL,
    desired_position            INTEGER         NOT NULL,

    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_calculations_symbol_date
    ON portfolio_calculations (symbol, date DESC);

    CREATE TABLE IF NOT EXISTS forecasts (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20)  NOT NULL,
    rule_name   VARCHAR(50)  NOT NULL,
    date        DATE         NOT NULL,
    raw_value   NUMERIC(10, 4),
    scaled_value NUMERIC(10, 4) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, rule_name, date)
);

CREATE INDEX IF NOT EXISTS idx_forecasts_symbol_date
    ON forecasts (symbol, date DESC);

    CREATE TABLE IF NOT EXISTS futures_prices (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20)    NOT NULL,
    date        DATE           NOT NULL,
    open        NUMERIC(12, 4),
    high        NUMERIC(12, 4),
    low         NUMERIC(12, 4),
    close       NUMERIC(12, 4) NOT NULL,
    volume      BIGINT,
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_futures_prices_symbol_date
    ON futures_prices (symbol, date DESC);
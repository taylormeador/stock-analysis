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

    CREATE TABLE instruments (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20)  NOT NULL UNIQUE,
    label           VARCHAR(20)  NOT NULL,
    multiplier      NUMERIC(12, 4) NOT NULL,
    asset_class     VARCHAR(20),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,  -- whether we want to generate forecasts
    notes           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Equity indices
INSERT INTO instruments (symbol, label, multiplier, asset_class, notes) VALUES
    ('MES=F', '/MES', 5,    'equity_index', 'Micro E-mini S&P 500'),
    ('MNQ=F', '/MNQ', 2,    'equity_index', 'Micro E-mini Nasdaq 100'),
    ('MYM=F', '/MYM', 0.5,  'equity_index', 'Micro E-mini Dow Jones'),
    ('M2K=F', '/M2K', 5,    'equity_index', 'Micro E-mini Russell 2000'),

-- Metals
    ('MGC=F', '/MGC', 10,   'metals', 'Micro Gold - 10 troy oz'),
    ('SIL=F', '/SIL', 1000, 'metals', 'Micro Silver - 1000 oz'),

-- Energy
    ('CL=F',  '/MCL', 100,  'energy', 'Using CL price as proxy for MCL - 100 barrel contract'),
    ('NG=F',  '/NG',  10000,'energy', 'Natural Gas - 10000 MMBtu, no micro available'),

-- Rates
    ('ZN=F',  '/ZN',  1000, 'rates', '10-Year Treasury Note'),
    ('ZT=F',  '/ZT',  2000, 'rates', '2-Year Treasury Note'),
    ('ZF=F',  '/ZF',  1000, 'rates', '5-Year Treasury Note'),

-- FX
    ('6E=F',  '/6E',  125000, 'fx', 'Euro FX - 125000 EUR'),
    ('6J=F',  '/6J',  12500000, 'fx', 'Japanese Yen - 12.5M JPY'),
    ('6B=F',  '/6B',  62500, 'fx', 'British Pound - 62500 GBP'),

-- Crypto
    ('MBT=F', '/MBT', 100,  'crypto', 'Micro Bitcoin - 0.1 BTC'),

-- Commodities
    ('ZC=F',  '/ZC',  50,   'commodities', 'Corn - 5000 bushels, $0.01/bushel = $50'),
    ('ZW=F',  '/ZW',  50,   'commodities', 'Wheat - 5000 bushels'),
    ('ZS=F',  '/ZS',  50,   'commodities', 'Soybeans - 5000 bushels')

ON CONFLICT (symbol) DO NOTHING;

CREATE TABLE strategies (
    id              SERIAL PRIMARY KEY,
    strategy_type   VARCHAR(50)  NOT NULL,
    parameters      JSONB        NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    notes           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE instrument_vol (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20)    NOT NULL,
    date            DATE           NOT NULL,
    short_term_vol  NUMERIC(12, 8) NOT NULL,
    long_term_vol   NUMERIC(12, 8) NOT NULL,
    blended_vol     NUMERIC(12, 8) NOT NULL,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, date)
);
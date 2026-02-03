
-- Historical stock price data table
CREATE TABLE stock_prices (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    volume BIGINT,

    sma_9 DECIMAL(10, 2),
    sma_10 DECIMAL(10, 2),
    sma_12 DECIMAL(10, 2),
    sma_26 DECIMAL(10, 2),
    sma_50 DECIMAL(10, 2),
    sma_100 DECIMAL(10, 2),
    sma_200 DECIMAL(10, 2),

    ema_9 DECIMAL(10, 2),
    ema_10 DECIMAL(10, 2),
    ema_12 DECIMAL(10, 2),
    ema_26 DECIMAL(10, 2),
    ema_50 DECIMAL(10, 2),
    ema_100 DECIMAL(10, 2),
    ema_200 DECIMAL(10, 2),

    rsi_14 DECIMAL(10, 2),
    macd_12_26_9 DECIMAL(10, 2),
    macdh_12_26_9 DECIMAL(10, 2),
    macds_12_26_9 DECIMAL(10, 2),

    bbl_20 DECIMAL(10, 2),
    bbm_20 DECIMAL(10, 2),
    bbu_20 DECIMAL(10, 2),
    bbb_20 DECIMAL(10, 2),
    bbp_20 DECIMAL(10, 2),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(ticker, date)
);

CREATE INDEX idx_stock_prices_ticker ON stock_prices(ticker);
CREATE INDEX idx_stock_prices_date ON stock_prices(date);
CREATE INDEX idx_stock_prices_ticker_date ON stock_prices(ticker, date);

CREATE TABLE cboe_daily_stats (
    date DATE PRIMARY KEY,
    total_put_call_ratio DECIMAL(5,2),
    equity_put_call_ratio DECIMAL(5,2),
    index_put_call_ratio DECIMAL(5,2),
    vix_put_call_ratio DECIMAL(5,2),
    total_volume BIGINT,
    total_oi BIGINT,
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_cboe_date ON cboe_daily_stats(date);

-- FRED macro economic indicators table
CREATE TABLE fred_macro_data (
    date DATE PRIMARY KEY,
    treasury_ten_year DECIMAL(6, 4),
    fed_funds_rate DECIMAL(6, 4),
    dollar_index DECIMAL(8, 4),
    unemployment_rate DECIMAL(5, 2),
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fred_macro_date ON fred_macro_data(date);


CREATE TABLE etl_task_status (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50),
    component_name VARCHAR(50),
    task_description VARCHAR(100),
    status VARCHAR(20),
    progress FLOAT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ
);

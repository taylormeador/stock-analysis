
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

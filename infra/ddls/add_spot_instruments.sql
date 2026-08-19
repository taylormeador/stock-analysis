-- Add price_source column to instruments table
ALTER TABLE instruments
ADD COLUMN IF NOT EXISTS price_source VARCHAR(20) NOT NULL DEFAULT 'futures_prices';

-- Deactivate all existing futures instruments
UPDATE instruments SET is_active = FALSE;

-- Add spot instruments (or reactivate if already present)
INSERT INTO instruments (symbol, label, multiplier, asset_class, price_source, is_active) VALUES
    ('^GSPC',   'SPX', 1, 'equity_index', 'stock_prices', TRUE),
    ('QQQ',     'QQQ', 1, 'equity_index', 'stock_prices', TRUE),
    ('IWM',     'IWM', 1, 'equity_index', 'stock_prices', TRUE),
    ('GLD',     'GLD', 1, 'metals',       'stock_prices', TRUE),
    ('BTC-USD', 'BTC', 1, 'crypto',       'stock_prices', TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    price_source = EXCLUDED.price_source,
    is_active    = EXCLUDED.is_active;

-- Ensure spot tickers are tracked for fetch_stock_data ingestion
INSERT INTO tickers (ticker, yf_ticker, is_tracked) VALUES
    ('^GSPC',   '^GSPC',   TRUE),
    ('QQQ',     'QQQ',     TRUE),
    ('IWM',     'IWM',     TRUE),
    ('GLD',     'GLD',     TRUE),
    ('BTC-USD', 'BTC-USD', TRUE)
ON CONFLICT DO NOTHING;

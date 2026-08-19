
-- Equity/ETF symbols to exclude from active-position metrics (buy-and-hold shares).
CREATE TABLE IF NOT EXISTS tastytrade_excluded_symbols (
    id              SERIAL PRIMARY KEY,
    account_number  VARCHAR(20) NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    UNIQUE (account_number, symbol)
);

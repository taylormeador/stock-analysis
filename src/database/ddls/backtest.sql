CREATE TABLE backtest_runs (
    id                  SERIAL PRIMARY KEY,
    strategy_type       VARCHAR(50) NOT NULL,
    ticker              VARCHAR(10) NOT NULL,
    start_date          DATE NOT NULL,
    end_date            DATE,
    parameters          JSONB NOT NULL,
    total_pnl           NUMERIC(12, 2),
    sharpe_ratio        NUMERIC(8, 4),
    max_drawdown        NUMERIC(8, 4),
    win_rate            NUMERIC(5, 4),
    close_reason_counts JSONB,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE backtest_transactions (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES backtest_runs(id),
    date            DATE NOT NULL,
    transaction_type VARCHAR(3) NOT NULL,  -- BTO, STO, BTC, STC
    strike          NUMERIC(10, 2) NOT NULL,
    expiration      DATE NOT NULL,
    bid             NUMERIC(10, 2) NOT NULL,
    ask             NUMERIC(10, 2) NOT NULL,
    fill_price      NUMERIC(10, 2) NOT NULL,
    quantity        INTEGER NOT NULL,
    pnl             NUMERIC(12, 2)
);

CREATE INDEX idx_transactions_run_id ON backtest_transactions(run_id);
CREATE INDEX idx_transactions_date ON backtest_transactions(date);
CREATE INDEX idx_runs_strategy_ticker ON backtest_runs(strategy_type, ticker);
CREATE TABLE backtest_runs (
    id                  SERIAL PRIMARY KEY,
    strategy_type       VARCHAR(50) NOT NULL,
    ticker              VARCHAR(10) NOT NULL,
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL ,
    parameters          JSONB NOT NULL,
    initial_debit       NUMERIC(12, 2),
    pnl                 NUMERIC(12, 2),
    fees                NUMERIC(10, 2),
    commissions         NUMERIC(10, 2),
    sharpe_ratio        NUMERIC(8, 4),
    sortino_ratio       NUMERIC(8, 4),
    max_drawdown        NUMERIC(8, 4),
    close_reason        VARCHAR(32),  -- stop_loss, profit_target, long_close_dte
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE backtest_transactions (
    id              SERIAL PRIMARY KEY,
    run_id           INTEGER NOT NULL REFERENCES backtest_runs(id),
    date             DATE NOT NULL,
    transaction_type VARCHAR(3) NOT NULL,  -- BTO, STO, BTC, STC
    strike          NUMERIC(10, 2) NOT NULL,
    expiration      DATE NOT NULL,
    bid             NUMERIC(10, 2) NOT NULL,
    ask             NUMERIC(10, 2) NOT NULL,
    fill_price      NUMERIC(10, 2) NOT NULL,
    quantity        INTEGER NOT NULL
);

CREATE INDEX idx_transactions_run_id ON backtest_transactions(run_id);
CREATE INDEX idx_transactions_date ON backtest_transactions(date);
CREATE INDEX idx_runs_strategy_ticker ON backtest_runs(strategy_type, ticker);
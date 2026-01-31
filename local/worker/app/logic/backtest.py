import pandas as pd
import logging

import app.database.db as db

logger = logging.getLogger(__name__)


def backtest(strategy, ticker: str, start_date: str, end_date: str):
    # get historical data
    # loop through and determine actions
    # calculate return, sharpe ration, drawdown, etc
    historical_sql = f"""
        SELECT *
        FROM stock_prices
        WHERE
            ticker = '{ticker}' AND
            date BETWEEN '{start_date}' AND '{end_date}';
    """
    with db.get_connection() as conn:
        historical_df = pd.read_sql(historical_sql, conn)

    # perform backtest with rsi thresholds, buy/sell entire position at once
    buy_rsi = 30
    sell_rsi = 70
    cash = 10000  # amount of money in account which is not invested
    position = 0  # num of shares in open position
    results = []
    for _, row in historical_df.iterrows():
        # If we have cash, look for buy signal
        # If we have a position, look for sell signal
        if cash:
            if row.rsi_14 <= buy_rsi:  # buy with all cash
                position = cash / row.close
                cash = 0

        elif position:
            if row.rsi_14 >= sell_rsi:
                cash = row.close * position
                position = 0

        results.append({"cash": cash, "position": position})

    breakpoint()

    # return BacktestResult


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    strategy = "test"
    ticker = "AAPL"
    start_date = "2023-01-01"
    end_date = "2025-01-01"
    backtest(strategy, ticker, start_date, end_date)

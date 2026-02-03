import pandas as pd
import logging

import app.database.db as db

logger = logging.getLogger(__name__)


class Strategy:
    def __init__(self):
        pass

    def generate_signals(self, data: pd.Series):
        raise NotImplementedError(
            f"generate_signals is not implemented for {self.__class__.__name__}"
        )


class RSIStrategy(Strategy):
    def __init__(self, buy_threshold: float, sell_threshold: float):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def generate_signals(self, data: pd.Series):
        signal = ""
        if data.rsi_14 <= self.buy_threshold:
            signal = "BUY"

        elif data.rsi_14 >= self.sell_threshold:
            signal = "SELL"

        return signal


class Portfolio:
    def __init__(self, initial_value: float):
        self.cash = initial_value
        self.num_shares = 0

    def portfolio_value(self, share_price: float) -> float:
        position_value = self.num_shares * share_price
        return self.cash + position_value


class Backtest:
    def __init__(
        self,
        strategy: Strategy,
        portfolio: Portfolio,
        ticker: str,
        start_date: str,
        end_date: str,
    ):
        self.strategy = strategy
        self.portfolio = portfolio
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.historical_data = self._get_historical_data()

    def _get_historical_data(self):
        historical_sql = f"""
            SELECT *
            FROM stock_prices
            WHERE
                ticker = '{self.ticker}' AND
                date BETWEEN '{self.start_date}' AND '{self.end_date}';
        """
        with db.get_connection() as conn:
            historical_df = pd.read_sql(historical_sql, conn)

        if not historical_df.empty:
            return historical_df

        raise ValueError("no data for given date range")

    def run(self):
        num_buys = 0
        num_sells = 0
        results = []
        for _, row in self.historical_data.iterrows():
            signal = strategy.generate_signals(row)

            # If there is a buy signal and we have cash, full port
            if self.portfolio.cash > 0 and signal == "BUY":
                self.portfolio.num_shares = self.portfolio.cash / row.close
                self.portfolio.cash = 0
                num_buys += 1

            # If there is a sell signal and we have shares, dump them
            if self.portfolio.num_shares and signal == "SELL":
                self.portfolio.cash = self.portfolio.num_shares * row.close
                self.portfolio.num_shares = 0
                num_sells += 1

            results.append(
                {
                    "cash": self.portfolio.cash,
                    "num_shares": self.portfolio.num_shares,
                    "num_buys": num_buys,
                    "num_sells": num_sells,
                }
            )

        return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    strategy = RSIStrategy(buy_threshold=40, sell_threshold=80)
    # strategy = Strategy(indicator="sma_9", buy_threshold=0, sell_threshold=0)

    ticker = "AAPL"
    start_date = "2023-01-01"
    end_date = "2025-01-01"
    initial_value = 10000
    portfolio = Portfolio(initial_value)
    backtest = Backtest(strategy, portfolio, ticker, start_date, end_date)
    results = backtest.run()

    logger.info(results[-1])

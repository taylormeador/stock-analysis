import pandas as pd
import logging
from typing import Dict

import app.database.db as db

logger = logging.getLogger(__name__)


class Strategy:
    def __init__(self):
        pass

    def generate_signals(self, data: pd.Series):
        raise NotImplementedError(
            f"generate_signals is not implemented for {self.__class__.__name__}"
        )


class RSI(Strategy):
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


class BacktestConfig:
    def __init__(self, params: Dict):
        self.required_fields = (
            "strategy",
            "ticker",
            "start_date",
            "end_date",
            "initial_value",
        )
        for field in self.required_fields:
            if field not in params:
                raise ValueError(f"{field} not found in backtest_params keys")

        self.strategy = strategies[params["strategy"]]
        self.ticker = params["ticker"]
        self.start_date = params["start_date"]
        self.end_date = params["end_date"]
        self.initial_value = params["initial_value"]

        self.portfolio = Portfolio(self.initial_value)


class Backtest:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.historical_data = self._get_historical_data()

    def _get_historical_data(self):
        historical_sql = f"""
            SELECT *
            FROM stock_prices
            WHERE
                ticker = '{self.config.ticker}' AND
                date BETWEEN '{self.config.start_date}' AND '{self.config.end_date}';
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
            if self.config.portfolio.cash > 0 and signal == "BUY":
                self.config.portfolio.num_shares = (
                    self.config.portfolio.cash / row.close
                )
                self.config.portfolio.cash = 0
                num_buys += 1

            # If there is a sell signal and we have shares, dump them
            if self.config.portfolio.num_shares and signal == "SELL":
                self.config.portfolio.cash = (
                    self.config.portfolio.num_shares * row.close
                )
                self.config.portfolio.num_shares = 0
                num_sells += 1

            results.append(
                {
                    "cash": self.config.portfolio.cash,
                    "num_shares": self.config.portfolio.num_shares,
                    "num_buys": num_buys,
                    "num_sells": num_sells,
                }
            )

        return results


strategies = {"rsi": RSI}


def run(params: Dict):
    config = BacktestConfig(params)
    backtest = Backtest(config)
    results = backtest.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

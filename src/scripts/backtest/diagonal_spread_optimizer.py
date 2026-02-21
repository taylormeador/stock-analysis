import itertools
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator, Literal

import db as db
import pandas as pd
from sqlalchemy import text

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

TICKERS = [
    "SPY",
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "NVDA",
    "JPM",
    "BAC",
    "GS",
    "V",
    "JNJ",
    "UNH",
    "PFE",
    "WMT",
    "HD",
    "MCD",
    "NKE",
    "XOM",
    "CVX",
    "XLE",
    "TSLA",
    "AMD",
    "COIN",
]


def get_options_data(
    ticker: str,
    start_date: str = "2021-01-01",
    end_date: str = "2021-12-31",
):
    sql = f"""
        SELECT
            quote_date,
            ticker,
            underlying_price,
            expiration,
            strike,
            bid,
            ask,
            delta
        FROM td_eod_options
        WHERE
            quote_date BETWEEN '{start_date}' AND '{end_date}' AND
            call_put = 'CALL' AND
            ticker = '{ticker}';
    """
    with db.get_connection() as conn:
        result = conn.execute(text(sql))
        data = result.fetchall()

    df = pd.DataFrame(data)
    float_cols = ["underlying_price", "bid", "ask", "delta"]
    df[float_cols] = df[float_cols].astype(float)

    return df


class DiagonalSpread:
    def __init__(
        self,
        long_call: pd.Series,
        short_call: pd.Series,
        stop_loss: float,
        profit_target: float,
        long_slippage: float,
        short_slippage: float,
    ):
        self.long_call = long_call
        self.short_call = short_call
        self.long_slippage = long_slippage
        self.short_slippage = short_slippage

        self.initial_debit, self.initial_long_value, self.initial_short_value = (
            self._calc_price(long_slippage, short_slippage)
        )
        self.current_value = self.initial_debit
        self.current_long_value = self.initial_long_value
        self.current_short_value = self.initial_short_value
        self.stop_loss_value = self.initial_debit * (1 - stop_loss)
        self.profit_target_value = self.initial_debit * (1 + profit_target)
        self.pnl = 0.0

        self._log_entry()

    def __repr__(self) -> str:
        return (
            f"DiagonalSpread("
            f"long={self.long_call.strike}c {self.long_call.expiration}, "
            f"short={self.short_call.strike}c {self.short_call.expiration}, "
            f"value={self.current_value:.2f}, "
            f"entry={self.initial_debit:.2f}, "
            f"pnl={self.pnl:.2f}, "
            f"stop={self.stop_loss_value:.2f}, "
            f"target={self.profit_target_value:.2f})"
        )

    def __str__(self) -> str:
        pnl_pct = ((self.current_value - self.initial_debit) / self.initial_debit) * 100
        return (
            "\n\n"
            f"{'Long':<6} {self.long_call.strike:>7.1f}c  exp={self.long_call.expiration}\n"
            f"{'Short':<6} {self.short_call.strike:>7.1f}c  exp={self.short_call.expiration}\n"
            f"{'Entry':<8} ${self.initial_debit:>8.2f}  |  "
            f"{'Current':<8} ${self.current_value:>8.2f}  |  "
            f"{'P&L':<4} {pnl_pct:>+7.1f}%\n"
            f"{'Stop':<8} ${self.stop_loss_value:>8.2f}  |  "
            f"{'Target':<8} ${self.profit_target_value:>8.2f}"
            "\n\n"
        )

    def _calc_price(
        self,
        long_slippage: float,
        short_slippage: float,
    ) -> tuple[float, float, float]:
        """
        Calculate the value of the spread, assuming fills happen
        closer to bid and ask for short and long calls, respectively.
        """
        long_spread = self.long_call.ask - self.long_call.bid
        # TODO what threshold do we want to maybe not trade an option at?
        if long_spread > 1:
            logger.warning(f"Illiquid option bid/ask spread: ${long_spread}")

        approx_long_slippage = long_spread * long_slippage
        long_price = round(self.long_call.bid + approx_long_slippage, 2)

        short_spread = self.short_call.ask - self.short_call.bid
        if short_spread > 1:
            logger.warning(f"Illiquid option bid/ask spread: ${short_spread}")

        approx_short_spread = short_spread * short_slippage
        short_price = round(self.short_call.bid + approx_short_spread, 2)

        value = long_price - short_price

        logger.info(self)
        logger.info("*" * 100)

        return value, long_price, short_price

    def _log_entry(self):
        logger.info("*" * 100)
        logger.info("Opening position")
        logger.info(self)

    def calc_position_value(self, current_chain: pd.DataFrame):
        """
        Calculate the value of the position on the date in the current chain.

        The procedure is done by finding our options in the current chain,
        and updating instance vars with the new data, then running the calculation.
        """
        logger.info(f"Calculating position value on {current_chain.quote_date.iloc[0]}")
        expiration_mask = current_chain.expiration == self.long_call.expiration
        strike_mask = current_chain.strike == self.long_call.strike
        long_call = current_chain[expiration_mask & strike_mask]
        if len(long_call) != 1:
            raise ValueError("Something wrong while finding long call value")

        self.long_call = long_call.iloc[0]

        expiration_mask = current_chain.expiration == self.short_call.expiration
        strike_mask = current_chain.strike == self.short_call.strike
        short_call = current_chain[expiration_mask & strike_mask]
        if len(current_chain[expiration_mask & strike_mask]) != 1:
            raise ValueError("Something wrong while finding short call value")

        self.short_call = short_call.iloc[0]

        self.current_value, self.long_value, self.short_value = self._calc_price(
            self.long_slippage, self.short_slippage
        )


@dataclass
class StrategyParams:
    long_delta: float
    long_dte: int
    long_slippage: float
    short_delta: float
    short_dte: int
    short_slippage: float
    short_close_delta: float
    short_close_dte: int
    short_close_profit: float
    stop_loss: float
    profit_target: float

    @classmethod
    def generate_grid(cls, grid: dict) -> Iterator["StrategyParams"]:
        for combo in itertools.product(*grid.values()):
            yield cls(**dict(zip(grid.keys(), combo)))


class DiagonalSpreadStrategy:
    def __init__(self, strategy_params: StrategyParams):
        self.params = strategy_params
        self.position = None

    def _find_call(
        self,
        current_chain: pd.DataFrame,
        long_short: Literal["long", "short"],
    ) -> pd.Series:
        if long_short == "long":
            dte = self.params.long_dte
            delta = self.params.long_delta
        elif long_short == "short":
            dte = self.params.short_dte
            delta = self.params.short_delta
        else:
            raise ValueError("unknown call type")

        dte_deltas = (
            current_chain.expiration - current_chain.quote_date - timedelta(days=dte)
        ).abs()
        right_dte = current_chain[dte_deltas == dte_deltas.min()]
        delta_deltas = (delta - right_dte.delta).abs()
        # TODO what if there are no calls? e.g. we are at the end of the dataset
        # TODO optimize which call we buy - more liquid/closer to even multiple of 5 means better fill and is more realistic.

        call = current_chain.loc[delta_deltas.idxmin()]
        if call.empty:
            raise ValueError("no call found")

        return call  # type: ignore

    def _roll_short_call(self, current_chain: pd.DataFrame):
        if not self.position:
            raise ValueError("no position to roll")

        # Bank the "profit" or "loss"
        self.position.pnl += (
            self.position.initial_short_value - self.position.short_value
        )

        # Find a new short call
        # Update the position to include the short call
        # Recalculate position value to populate correct instance vars
        self.position.short_call = self._find_call(current_chain, "short")
        self.position.calc_position_value(current_chain)
        self.position.initial_short_value = self.position.current_short_value

    def _log_start(self):
        sql = """
            INSERT INTO backtest_runs (
                strategy_type,
                ticker,
                start_date,
                end_date,
                parameters,
                created_at
            )
            VALUES (
                :strategy_type,
                :ticker,
                :start_date,
                :end_date,
                :parameters,
                :created_at
            );
        """
        logger.info(f"TODO {sql}")
        # sql_params = {
        #     "strategy_type": "diagonal_spread",
        #     "ticker": df.ticker.iloc[0],
        #     "start_date": start_date,
        #     "end_date": df.quote_date.max(),
        #     "parameters": self.params,
        #     "created_at": datetime.now(timezone.utc),
        # }
        # with db.get_connection() as conn:
        #     conn.execute(text(sql), parameters=sql_params)

    def run(self, df) -> DiagonalSpread:
        # TODO account for transaction fees and commissions

        # TODO I think we need to make start date an input parameter for each position
        # TODO does it make more sense to loop over quote_date.unique()
        start_date = df.quote_date.min()
        dates = [
            start_date + timedelta(days=i) for i in range(self.params.long_dte + 1)
        ]

        logger.info(f"running strategy with params: {self.params}")
        for _, current_date in enumerate(dates):
            current_chain = df[df.quote_date == current_date]
            if current_chain.empty:
                continue

            # On the first day of the simulation, open the spread
            if not self.position:
                long_call = self._find_call(current_chain, "long")
                short_call = self._find_call(current_chain, "short")
                self.position = DiagonalSpread(
                    long_call=long_call,
                    short_call=short_call,
                    stop_loss=self.params.stop_loss,
                    profit_target=self.params.profit_target,
                    long_slippage=self.params.long_slippage,
                    short_slippage=self.params.short_slippage,
                )
            self.position.calc_position_value(current_chain)

            # If below stop_loss, close position and end run
            if self.position.current_value < self.position.stop_loss_value:
                logger.info("*" * 100)
                logger.info(f"Stop loss reached on {current_date}")
                logger.info(f"Position value: {self.position.current_value}")
                logger.info(f"Stop loss value: {self.position.stop_loss_value}")
                logger.info("*" * 100)
                return self.position
                # TODO how to end run?

            # If profit target is reached, close position and end run
            if self.position.current_value > self.position.profit_target_value:
                logger.info("*" * 100)
                logger.info(f"Profit target reached on {current_date}")
                logger.info(f"Position value: {self.position.current_value}")
                logger.info(f"Profit target value: {self.position.profit_target_value}")
                logger.info("*" * 100)
                return self.position
                # TODO how to end run?

            # If the short call hits the profit target, roll down and out
            if self.position.short_value <= self.position.initial_short_value * (
                1 - self.params.short_close_delta
            ):
                logger.info("*" * 100)
                logger.info("Rolling call down and out")
                self._roll_short_call(current_chain)

            # If the short call is being threatened, roll up and out
            # TODO this is tricky because in reality I would try to roll for a tiny credit,
            # not necessarily based on strike/expiration
            elif self.position.short_call.delta >= self.params.short_close_delta:
                logger.info("*" * 100)
                logger.info("Rolling call up and out")
                self._roll_short_call(current_chain)

            # Close short call when DTE is below threshold
            elif self.position.short_call.expiration - current_date <= timedelta(
                days=self.params.short_close_dte
            ):
                logger.info("*" * 100)
                logger.info("Rolling short call due to DTE")
                self._roll_short_call(current_chain)

        return self.position  # type: ignore


def main():
    """
    For the first round of backtesting diagonal spreads, we are going to
    buy one diagonal spread each day based on the close price of the previous day.

    The spread will be closed and run ended if the position falls below the stop_loss value.
    The short call will be rolled (offensively) at short_close % of the max profit of the short call at entry.
    The short call will be rolled (defensively) at short_roll delta. If it cannot be rolled to the desired strike/DTE TODO
    The entire position will be closed and the run ended at close_at % profit of the entry debit.
    """

    # TODO output metrics, log to mlflow

    param_grid = {
        "long_delta": [0.9, 0.8, 0.7, 0.6],
        "long_dte": [180, 270, 365],
        "long_slippage": [0.75],
        "short_delta": [0.2, 0.3],
        "short_dte": [28, 35, 42],
        "short_slippage": [0.25],
        "short_close_delta": [0.4, 0.5, 0.6],  # delta at which to roll short strike
        "short_close_dte": [7, 14, 21],  # DTE at which to close short call
        "short_close_profit": [0.5, 0.75],  # percent of max profit of short call
        "stop_loss": [0.05, 0.1, 0.2, 0.3],  # percent decrease of entry debit
        "profit_target": [0.25, 0.50, 0.75],  # percent profit of entry debit
    }
    # TODO for ticker in TICKERS:
    for ticker in ("SPY", "AAPL"):
        options_df = get_options_data(ticker)
        for params in StrategyParams.generate_grid(param_grid):
            strategy = DiagonalSpreadStrategy(params)
            position = strategy.run(options_df)
            breakpoint()


if __name__ == "__main__":
    main()

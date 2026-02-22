import itertools
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterator, Literal
import numpy as np
import time

import db as db
import exchange_calendars as xcals
import pandas as pd
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
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
    start_date: str,
    end_date: str,
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

        return value, long_price, short_price

    def _log_entry(self):
        logger.debug("*" * 100)
        logger.debug("Opening position")
        logger.debug(self)

    def calc_position_value(self, current_chain: pd.DataFrame):
        """
        Calculate the value of the position on the date in the current chain.

        The procedure is done by finding our options in the current chain,
        and updating instance vars with the new data, then running the calculation.
        """
        logger.debug(
            f"Calculating position value on {current_chain.quote_date.iloc[0]}"
        )
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
            long_slippage=self.long_slippage,
            short_slippage=self.short_slippage,
        )


@dataclass
class StrategyParams:
    """
    Parameters for the diagonal spread strategy.

    long_delta: Target delta for the long call at entry
    long_dte: Target DTE for the long call at entry
    long_close_dte: DTE of the long call at which we close the entire position
    long_slippage: Percent of bid/ask spread paid for the long call (0.75 = closer to ask)
    short_delta: Target delta for the short call at entry
    short_dte: Target DTE for the short call at entry
    short_slippage: Percent of bid/ask spread paid for the short call (0.25 = closer to bid)
    short_close_delta: Delta at which to roll the short call defensively
    short_close_dte: DTE at which to roll the short call regardless of other conditions
    short_close_profit: Percent of max profit of short call at which to roll short call
    stop_loss: Percent decrease of entry debit at which to close the entire position
    profit_target: Percent increase of entry debit at which to close the entire position
    """

    long_delta: float
    long_dte: int
    long_close_dte: int
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


class TransactionType(Enum):
    BTO = "BTO"
    STO = "STO"
    BTC = "BTC"
    STC = "STC"


class DiagonalSpreadStrategy:
    def __init__(
        self,
        ticker: str,
        start_date: datetime,
        strategy_params: StrategyParams,
    ):
        self.params = strategy_params
        self.ticker = ticker
        self.position: DiagonalSpread | None = None
        self.start_date: datetime = start_date
        self.run_id: int = self._log_start()
        self.daily_values: dict[datetime, float] = {}

    def _log_start(self):
        sql = """
            INSERT INTO backtest_runs (
                strategy_type,
                ticker,
                start_date,
                parameters
            ) VALUES (
                :strategy_type,
                :ticker,
                :start_date,
                :parameters
            )
            RETURNING id;
        """
        sql_params = {
            "strategy_type": "DiagonalSpread",
            "ticker": self.ticker,
            "start_date": self.start_date,
            "parameters": json.dumps(asdict(self.params)),
        }
        with db.get_connection() as conn:
            result = conn.execute(text(sql), parameters=sql_params)
            run_id = result.scalar()
            conn.commit()

        if not run_id:
            raise RuntimeError("expected to get PK from insert")

        return run_id

    def end_run(self):
        if not self.position:
            raise RuntimeError("ended run with no position")

        sharpe, sortino, max_drawdown = self._calc_metrics()
        logger.debug(f"Sharpe: {sharpe}")
        logger.debug(f"Sortino: {sortino}")
        logger.debug(f"Max Drawdown: {max_drawdown}")

        sql = """
            UPDATE backtest_runs
            SET
                end_date = :end_date,
                total_pnl = :total_pnl,
                sharpe_ratio = :sharpe_ratio,
                sortino_ratio = :sortino_ratio,
                max_drawdown = :max_drawdown,
                close_reason = :close_reason
            WHERE id = :run_id;
        """
        params = {
            "end_date": self.end_date,
            "total_pnl": float(self.position.pnl),
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown": float(max_drawdown),
            "close_reason": self.close_reason,
            "run_id": self.run_id,
        }
        with db.get_connection() as conn:
            conn.execute(text(sql), params)
            conn.commit()

    def _calc_metrics(self, risk_free_rate: float = 0.0):
        # TODO get 3 month T bill from FRED, averaged over the period for the risk free rate
        values = pd.Series(self.daily_values)
        returns = values.pct_change().dropna()
        excess_returns = returns - (risk_free_rate / 252)

        sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252)

        downside = excess_returns[excess_returns < 0]
        sortino = (excess_returns.mean() / downside.std()) * np.sqrt(252)

        max_drawdown = (values / values.cummax() - 1).min()

        return sharpe, sortino, max_drawdown

    def _insert_tx(
        self,
        date: str,
        transaction_type: TransactionType,
        strike: float,
        expiration: str,
        bid: float,
        ask: float,
        fill_price: float,
        quantity: int,
    ):
        sql = """
            INSERT INTO backtest_transactions (
                run_id, date, transaction_type, strike, expiration, bid, ask, fill_price, quantity
            ) VALUES (
                :run_id, :date, :transaction_type, :strike, :expiration, :bid, :ask, :fill_price, :quantity
            );
        """
        params = {
            "run_id": self.run_id,
            "date": date,
            "transaction_type": transaction_type.value,
            "strike": float(strike),
            "expiration": expiration,
            "bid": float(bid),
            "ask": float(ask),
            "fill_price": float(fill_price),
            "quantity": int(quantity),
        }
        with db.get_connection() as conn:
            conn.execute(text(sql), parameters=params)
            conn.commit()

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
            logger.error("no call found")

        return call  # type: ignore

    def _open_position(self, current_chain):
        long_call = self._find_call(current_chain, "long")
        ideal_date = current_chain.quote_date.iloc[0] + timedelta(
            days=self.params.long_dte
        )
        if timedelta(days=-10) < long_call.expiration - ideal_date > timedelta(days=10):
            logger.warning("long call near desired DTE not found. Stopping run")
            return None

        short_call = self._find_call(current_chain, "short")

        position = DiagonalSpread(
            long_call=long_call,
            short_call=short_call,
            stop_loss=self.params.stop_loss,
            profit_target=self.params.profit_target,
            long_slippage=self.params.long_slippage,
            short_slippage=self.params.short_slippage,
        )

        self._insert_tx(
            date=current_chain.quote_date.iloc[0],
            transaction_type=TransactionType.BTO,
            strike=long_call.strike,
            expiration=long_call.expiration,
            bid=long_call.bid,
            ask=long_call.ask,
            fill_price=position.current_long_value,
            quantity=1,
        )
        self._insert_tx(
            date=current_chain.quote_date.iloc[0],
            transaction_type=TransactionType.STO,
            strike=short_call.strike,
            expiration=short_call.expiration,
            bid=short_call.bid,
            ask=short_call.ask,
            fill_price=position.current_short_value,
            quantity=1,
        )

        # -initial debit -$1 commision -$0.04 fee to open contract x 2
        position.pnl = -position.current_value - 0.0208

        return position

    def _close_position(self, current_chain):
        if not self.position:
            raise ValueError("no position to close")

        self.position.pnl += self.position.current_value
        self.end_date = current_chain.quote_date.iloc[0]

        # BTC short call + STC long call
        self._insert_tx(
            date=current_chain.quote_date.iloc[0],
            transaction_type=TransactionType.BTC,
            strike=self.position.short_call.strike,
            expiration=self.position.short_call.expiration,
            bid=self.position.short_call.bid,
            ask=self.position.short_call.ask,
            fill_price=self.position.current_short_value,
            quantity=1,
        )
        self._insert_tx(
            date=current_chain.quote_date.iloc[0],
            transaction_type=TransactionType.STC,
            strike=self.position.long_call.strike,
            expiration=self.position.long_call.expiration,
            bid=self.position.long_call.bid,
            ask=self.position.long_call.ask,
            fill_price=self.position.current_long_value,
            quantity=1,
        )

    def _roll_short_call(self, current_chain: pd.DataFrame):
        if not self.position:
            raise ValueError("no position to roll")

        # Bank the "profit" or "loss" and subtract commission + fees
        leg_pnl = self.position.initial_short_value - self.position.short_value
        self.position.pnl += leg_pnl - 0.0104

        # Log the BTC before we forget the data
        self._insert_tx(
            date=current_chain.quote_date.iloc[0],
            transaction_type=TransactionType.BTC,
            strike=self.position.short_call.strike,
            expiration=self.position.short_call.expiration,
            bid=self.position.short_call.bid,
            ask=self.position.short_call.ask,
            fill_price=self.position.current_short_value,
            quantity=1,
        )

        # Find a new short call
        # Update the position to include the short call
        # Recalculate position value to populate correct instance vars
        # Log to db
        self.position.short_call = self._find_call(current_chain, "short")
        self.position.calc_position_value(current_chain)
        self.position.initial_short_value = self.position.current_short_value
        self._insert_tx(
            date=current_chain.quote_date.iloc[0],
            transaction_type=TransactionType.STO,
            strike=self.position.short_call.strike,
            expiration=self.position.short_call.expiration,
            bid=self.position.short_call.bid,
            ask=self.position.short_call.ask,
            fill_price=self.position.current_short_value,
            quantity=1,
        )

    def run(self, df) -> DiagonalSpread:  # type: ignore
        run_dates = df[df.quote_date >= self.start_date.date()].quote_date.unique()
        run_dates = sorted(run_dates)

        logger.info(f"running strategy with params: {self.params}")
        for current_date in run_dates:
            current_chain = df[df.quote_date == current_date]
            if current_chain.empty:
                continue

            # On the first day of the simulation, open the spread
            if not self.position:
                self.position = self._open_position(current_chain)
                if self.position is None:
                    break

            self.position.calc_position_value(current_chain)

            # Log value before adjustments for simplicity.
            # Adjustments will be reflected in the next day's price
            self.daily_values[current_date] = self.position.current_value

            # If below stop_loss, close position and end run
            if self.position.current_value < self.position.stop_loss_value:
                logger.debug("*" * 100)
                logger.debug(f"Stop loss reached on {current_date}")
                logger.debug(self.position)
                self._close_position(current_chain)
                self.close_reason = "stop_loss"
                return self.position

            # If profit target is reached, close position and end run
            if self.position.current_value > self.position.profit_target_value:
                logger.debug("*" * 100)
                logger.debug("Profit target reached")
                logger.debug(self.position)
                self._close_position(current_chain)
                self.close_reason = "profit_target"
                return self.position

            # If the long call DTE is below threshold
            if self.position.long_call.expiration - current_date <= timedelta(
                days=self.params.long_close_dte
            ):
                logger.debug("*" * 100)
                logger.debug("Closing position due to DTE of long call")
                logger.debug(self.position)
                self._close_position(current_chain)
                self.close_reason = "long_close_dte"
                return self.position

            # If the short call hits the profit target, roll down and out
            if self.position.short_value <= self.position.initial_short_value * (
                1 - self.params.short_close_delta
            ):
                logger.debug("Rolling call down and out")
                self._roll_short_call(current_chain)

            # If the short call is being threatened, roll up and out
            # TODO this is tricky because in reality I would try to roll for a tiny credit,
            # not necessarily based on strike/expiration
            elif self.position.short_call.delta >= self.params.short_close_delta:
                logger.debug("Rolling call up and out")
                self._roll_short_call(current_chain)

            # Close short call when DTE is below threshold
            elif self.position.short_call.expiration - current_date <= timedelta(
                days=self.params.short_close_dte
            ):
                logger.debug("Rolling short call due to DTE")
                self._roll_short_call(current_chain)


def main():
    """
    For the first round of backtesting diagonal spreads, we are going to
    buy one diagonal spread each day based on the close price of the previous day.

    The spread will be closed and run ended if the position falls below the stop_loss value.
    The short call will be rolled (offensively) at short_close % of the max profit of the short call at entry.
    The short call will be rolled (defensively) at short_roll delta. If it cannot be rolled to the desired strike/DTE TODO
    The entire position will be closed and the run ended at close_at % profit of the entry debit.
    """

    param_grid = {
        "long_delta": [0.9, 0.8, 0.7, 0.6],
        "long_dte": [180, 270, 365],
        "long_close_dte": [75, 90, 105, 120],
        "long_slippage": [0.75],
        "short_delta": [0.2, 0.3],
        "short_dte": [28, 35, 42],
        "short_slippage": [0.25],
        "short_close_delta": [0.4, 0.5, 0.6],
        "short_close_dte": [7, 14, 21],
        "short_close_profit": [0.5, 0.75],
        "stop_loss": [0.05, 0.1, 0.2, 0.3],
        "profit_target": [0.25, 0.50, 0.75],
    }

    # Configure the date window that we want to open positions in
    window_start_date = "2021-01-01"
    window_end_date = "2021-06-01"

    # Get options data for start_date to end_date + max long_call dte
    dt_format = "%Y-%m-%d"
    window_end_date_dt = datetime.strptime(window_end_date, dt_format)
    delta = timedelta(days=max(param_grid["long_dte"]) + 15)
    options_end_date = (window_end_date_dt + delta).strftime(dt_format)

    # create date range for iterating
    cal = xcals.get_calendar("XNYS")
    date_range = cal.sessions_in_range(window_start_date, window_end_date)

    outer_start_time = time.perf_counter()
    i = 0
    ticker = "SPY"
    options_df = get_options_data(ticker, window_start_date, options_end_date)
    for start_date in date_range:
        for params in StrategyParams.generate_grid(param_grid):
            i += 1
            start_time = time.perf_counter()
            strategy = DiagonalSpreadStrategy(ticker, start_date, params)
            try:
                # TODO log to mlflow
                position = strategy.run(options_df)
                logger.debug("*" * 100)
                logger.debug("end position")
                logger.debug(position)
                strategy.end_run()
                logger.info(f"run finished in {time.perf_counter() - start_time:.2f}s")
            except:
                logger.exception("error in run()")
                breakpoint()
    logger.info(
        f"ran {i} historical backtests in {time.perf_counter() - outer_start_time:.2f}s"
    )


if __name__ == "__main__":
    main()

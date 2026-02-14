import itertools
import logging
from datetime import timedelta

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


def get_options_data(ticker: str, start_date: str = "2021-01-01"):
    sql = f"""
        SELECT
            date,
            ticker,
            expiration,
            strike,
            call_put,
            bid,
            ask,
            vol,
            delta,
            gamma,
            theta,
            vega,
            rho
        FROM pnp_option_chain
        WHERE
            date > '{start_date}' AND
            call_put = 'Call' AND
            ticker = '{ticker}';
    """
    with db.get_connection() as conn:
        result = conn.execute(text(sql))
        data = result.fetchall()

    df = pd.DataFrame(data)

    float_cols = ["bid", "ask", "vol", "delta", "gamma", "theta", "vega", "rho"]
    df[float_cols] = df[float_cols].astype(float)

    return df


# TODO output metrics, log to mlflow

PARAMS = {
    "long_delta": [0.9, 0.8, 0.7, 0.6],
    "long_dte": [60],
    "short_delta": [0.2, 0.3],
    "short_dte": [14, 21],
    "short_close": [0.5, 0.75],  # percent of max profit of short call
    "short_roll": [0.4, 0.5],  # delta at which to roll short strike
    "stop_loss": [-0.1, -0.2, -0.3],  # percent decrease of entry debit
    "close_at": [0.25, 0.50, 0.75],  # percent profit of entry debit
}


class DiagonalSpread:
    def __init__(self, long_call: pd.Series, short_call: pd.Series):
        self.long_call = long_call
        self.short_call = short_call

        self._log_entry()
        self.initial_debit = self._calc_price()
        self.current_value = self.initial_debit

    def _calc_price(
        self,
        long_slippage: float = 0.75,
        short_slippage: float = 0.25,
    ) -> float:
        """
        Calculate the value of the spread, assuming fills happen
        closer to bid and ask for short and long calls, respectively.
        """
        long_spread = self.long_call.ask - self.long_call.bid
        if (
            long_spread > 1
        ):  # TODO what threshold do we want to maybe not trade an option at?
            logger.warning(f"Illiquid option bid/ask spread: ${long_spread}")

        approx_long_slippage = long_spread * long_slippage
        long_price = round(self.long_call.bid + approx_long_slippage, 2)
        logger.debug(f"long_price: ${long_price}")

        short_spread = self.short_call.ask - self.short_call.bid
        if short_spread > 1:
            logger.warning(f"Illiquid option bid/ask spread: ${short_spread}")

        approx_short_spread = short_spread * short_slippage
        short_price = round(self.short_call.bid + approx_short_spread, 2)
        logger.debug(f"short_price: ${short_price}")

        value = long_price - short_price
        logger.info(f"Spread value: ${value}")

        logger.info("*" * 100)

        return value

    def _log_entry(self):
        logger.info("*" * 100)
        logger.info("Opening position")
        logger.info(f"long_call:\n{self.long_call}")
        logger.info(f"short_call:\n{self.short_call}")

    def calc_position_value(self, chain: pd.Series) -> float:
        """
        Calculate the value of the position on the date given by `chain`.
        `chain` is a row from the option chain data for one day.
        The procedure is done by finding our options in the current chain,
        and updating instance vars with the new data, then running the calculation.
        """
        logger.info(f"Calculating position value on {chain.date.iloc[0]}")
        expiration_mask = chain.expiration == self.long_call.expiration
        strike_mask = chain.strike == self.long_call.strike
        long_call = chain[expiration_mask & strike_mask]
        if len(long_call) != 1:
            raise ValueError("Something wrong while finding long call value")

        self.long_call = long_call.iloc[0]

        expiration_mask = chain.expiration == self.short_call.expiration
        strike_mask = chain.strike == self.short_call.strike
        short_call = chain[expiration_mask & strike_mask]
        if len(chain[expiration_mask & strike_mask]) != 1:
            raise ValueError("Something wrong while finding short call value")

        self.short_call = short_call.iloc[0]

        return self._calc_price()


def run_strategy(params, df):
    long_delta = params[0]
    long_dte = params[1]
    short_delta = params[2]
    short_dte = params[3]
    short_close = params[4]
    short_roll = params[5]
    stop_loss = params[6]
    close_at = params[7]

    # TODO I think we need to make start date an input parameter for each position
    start_date = df.date.min()
    dates = [start_date + timedelta(days=i) for i in range(long_dte + 1)]
    position = None
    for i, current_date in enumerate(dates):
        # Skip days with no options data
        if current_date not in df.date.unique():
            continue

        # On the first day of the simulation, open the spread
        if not position:
            today = df[df.date == current_date]

            # Get the calls with the closest dte/delta to target
            dte_deltas = (
                today.expiration - current_date - timedelta(days=long_dte)
            ).abs()
            right_dte = today[dte_deltas == dte_deltas.min()]
            delta_deltas = (long_delta - right_dte.delta).abs()
            # TODO what if there are no calls? e.g. we are at the end of the dataset
            long_call = df.iloc[delta_deltas.idxmin()]

            dte_deltas = (
                today.expiration - current_date - timedelta(days=short_dte)
            ).abs()
            right_dte = today[dte_deltas == dte_deltas.min()]
            delta_deltas = (short_delta - right_dte.delta).abs()
            short_call = df.iloc[delta_deltas.idxmin()]

            position = DiagonalSpread(long_call, short_call)

        # Calculate value of position on this day
        # If below stop_loss, close position and end run
        # If short_roll or short_close is triggered, do that
        # If close_at is triggered, do that
        current_chain = df[df.date == current_date]

        # TODO this is a temporary check to get around bad data quality
        if position.long_call.strike not in current_chain.strike.unique():
            logger.info(f"skipping day {current_date}")
            continue
        if position.short_call.strike not in current_chain.strike.unique():
            logger.info(f"skipping day {current_date}")
            continue
        position.current_value = position.calc_position_value(current_chain)


def main():
    """
    For the first round of backtesting diagonal spreads, we are going to
    buy one diagonal spread each day based on the close price of the previous day.

    The spread will be closed and run ended if the position falls below the stop_loss value.
    The short call will be rolled (offensively) at short_close % of the max profit of the short call at entry.
    The short call will be rolled (defensively) at short_roll delta. If it cannot be rolled to the desired strike/DTE TODO
    The entire position will be closed and the run ended at close_at % profit of the entry debit.
    """
    # for ticker in TICKERS:
    param_combos = itertools.product(*PARAMS.values())
    for ticker in ("SPY", "AAPL"):
        options_df = get_options_data(ticker)
        for params in param_combos:
            run_strategy(params, options_df)


if __name__ == "__main__":
    main()

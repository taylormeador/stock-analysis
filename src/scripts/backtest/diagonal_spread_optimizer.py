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
    ):
        self.long_call = long_call
        self.short_call = short_call

        self.initial_debit, self.initial_long_value, self.initial_short_value = (
            self._calc_price()
        )
        self.current_value = self.initial_debit
        self.current_long_value = self.initial_long_value
        self.current_short_value = self.initial_short_value
        self.stop_loss_value = self.initial_debit * (1 - stop_loss)
        self.profit_target_value = self.initial_debit * (1 + profit_target)
        self.pnl = 0.0

        self._log_entry()

    def _calc_price(
        self,
        long_slippage: float = 0.75,
        short_slippage: float = 0.25,
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
        logger.debug(f"Long value: ${long_price}")

        short_spread = self.short_call.ask - self.short_call.bid
        if short_spread > 1:
            logger.warning(f"Illiquid option bid/ask spread: ${short_spread}")

        approx_short_spread = short_spread * short_slippage
        short_price = round(self.short_call.bid + approx_short_spread, 2)
        logger.debug(f"Short value: ${short_price}")

        value = long_price - short_price
        logger.info(f"Spread value: ${value}")

        logger.info("*" * 100)

        return value, long_price, short_price

    def _log_entry(self):
        logger.info("*" * 100)
        logger.info("Opening position")
        logger.info(f"long_call:\n{self.long_call}")
        logger.info(f"short_call:\n{self.short_call}")
        logger.info(f"spread value: {self.current_value}")
        logger.info(f"stop loss value: {self.stop_loss_value}")
        logger.info(f"profit target value: {self.profit_target_value}")

    def calc_position_value(self, chain: pd.Series):
        """
        Calculate the value of the position on the date given by `chain`.
        `chain` is a row from the option chain data for one day.
        The procedure is done by finding our options in the current chain,
        and updating instance vars with the new data, then running the calculation.
        """
        logger.info(f"Calculating position value on {chain.quote_date.iloc[0]}")
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

        self.current_value, self.long_value, self.short_value = self._calc_price()


def run_strategy(params, df):
    long_delta = params[0]
    long_dte = params[1]
    short_delta = params[2]
    short_dte = params[3]
    short_close = params[4]
    short_roll = params[5]
    stop_loss = params[6]
    profit_target = params[7]

    logger.info(f"running strategy with params: {params}")

    # TODO I think we need to make start date an input parameter for each position
    # TODO does it make more sense to loop over quote_date.unique()
    start_date = df.quote_date.min()
    dates = [start_date + timedelta(days=i) for i in range(long_dte + 1)]
    position = None
    for i, current_date in enumerate(dates):
        # Skip days with no options data
        if current_date not in df.quote_date.unique():
            continue

        # On the first day of the simulation, open the spread
        if not position:
            today = df[df.quote_date == current_date]

            # Get the calls with the closest dte/delta to target
            dte_deltas = (
                today.expiration - current_date - timedelta(days=long_dte)
            ).abs()
            right_dte = today[dte_deltas == dte_deltas.min()]
            delta_deltas = (long_delta - right_dte.delta).abs()
            # TODO what if there are no calls? e.g. we are at the end of the dataset
            # TODO optimize which call we buy - more liquid/closer to even multiple of 5 means better fill and is more realistic.
            long_call = df.iloc[delta_deltas.idxmin()]

            dte_deltas = (
                today.expiration - current_date - timedelta(days=short_dte)
            ).abs()
            right_dte = today[dte_deltas == dte_deltas.min()]
            delta_deltas = (short_delta - right_dte.delta).abs()
            short_call = df.iloc[delta_deltas.idxmin()]

            position = DiagonalSpread(long_call, short_call, stop_loss, profit_target)

        # Calculate value of position on this da
        today = df[df.quote_date == current_date]
        position.calc_position_value(today)

        # If below stop_loss, close position and end run
        if position.current_value < position.stop_loss_value:
            logger.info("*" * 100)
            logger.info(f"Stop loss reached on {current_date}")
            logger.info(f"Position value: {position.current_value}")
            logger.info(f"Stop loss value: {position.stop_loss_value}")
            logger.info("*" * 100)
            return position
            # TODO end run

        # If profit target is reached, close position and end run
        if position.current_value > position.profit_target_value:
            logger.info("*" * 100)
            logger.info(f"Profit target reached on {current_date}")
            logger.info(f"Position value: {position.current_value}")
            logger.info(f"Profit target value: {position.profit_target_value}")
            logger.info("*" * 100)
            return position

        # If the short call hits the profit target, roll down and out
        if position.short_value < position.initial_short_value * (1 - short_close):
            logger.info("*" * 100)
            logger.info("Rolling call down and out")

            # Bank the "profit"
            profit = position.initial_short_value - position.short_value
            position.pnl += profit

            # Find a new short call
            dte_deltas = (
                today.expiration - current_date - timedelta(days=short_dte)
            ).abs()
            right_dte = today[dte_deltas == dte_deltas.min()]
            delta_deltas = (short_delta - right_dte.delta).abs()
            short_call = df.iloc[delta_deltas.idxmin()]

            # Update the position to include the short call
            # Recalculate position value to populate correct instance vars
            position.short_call = short_call
            position.calc_position_value(today)
            position.initial_short_value = position.current_short_value

        # If the short call is being threatened, roll up and out
        # TODO this is tricky because in reality I would try to roll for a tiny credit,
        # not necessarily based on strike/expiration
        elif position.short_call.delta > short_roll:
            logger.info("*" * 100)
            logger.info("Rolling call up and out")

            # Take the "loss"
            # TODO is this necessarily a loss? Can it be that delta has increased from our entry but the value of the option has decreased?
            # This could happen due to vega/IV in some cases I think
            loss = position.initial_short_value - position.short_value
            position.pnl += loss

            # Find a new short call
            dte_deltas = (
                today.expiration - current_date - timedelta(days=short_dte)
            ).abs()
            right_dte = today[dte_deltas == dte_deltas.min()]
            delta_deltas = (short_delta - right_dte.delta).abs()
            short_call = df.iloc[delta_deltas.idxmin()]

            # Update the position to include the short call
            # Recalculate position value to populate correct instance vars
            position.short_call = short_call
            position.calc_position_value(today)
            position.initial_short_value = position.current_short_value

        # TODO implement closing short call for DTE proximity

    return position


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

    PARAMS = {
        "long_delta": [0.9, 0.8, 0.7, 0.6],
        "long_dte": [180, 270, 365],
        "short_delta": [0.2, 0.3],
        "short_dte": [28, 35, 42],
        "short_close_delta": [0.5, 0.75],  # percent of max profit of short call
        "short_close_dte": [7, 14, 21],  # DTE at which to close short call
        "short_roll": [0.4, 0.5],  # delta at which to roll short strike
        "stop_loss": [0.05, 0.1, 0.2, 0.3],  # percent decrease of entry debit
        "profit_target": [0.25, 0.50, 0.75],  # percent profit of entry debit
    }
    # for ticker in TICKERS:
    param_combos = itertools.product(*PARAMS.values())
    for ticker in ("SPY", "AAPL"):
        options_df = get_options_data(ticker)
        for params in param_combos:
            end_position = run_strategy(params, options_df)
            breakpoint()


if __name__ == "__main__":
    main()

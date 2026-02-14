import itertools
from datetime import timedelta

import db as db
import pandas as pd
from sqlalchemy import text

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
    "long_dte": [180, 270, 365],
    "short_delta": [0.2, 0.3],
    "short_dte": [21, 30, 45],
    "short_close": [0.5, 0.75],  # percent of max profit of short call
    "short_roll": [0.4, 0.5],  # delta at which to roll short strike
    "stop_loss": [-0.1, -0.2, -0.3],  # percent decrease of entry debit
    "close_at": [0.25, 0.50, 0.75],  # percent profit of entry debit
}


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

            breakpoint()

            # Get the calls with the closest dte/delta to target
            dte_deltas = (
                today.expiration - current_date - timedelta(days=long_dte)
            ).abs()
            right_dte = df[dte_deltas == dte_deltas.min()]
            delta_deltas = (long_delta - right_dte.delta).abs()
            long_call = df.iloc[delta_deltas.idxmin()]

            dte_deltas = (
                today.expiration - current_date - timedelta(days=long_dte)
            ).abs()
            right_dte = df[dte_deltas == dte_deltas.min()]
            delta_deltas = (short_delta - right_dte.delta).abs()
            short_call = df.iloc[delta_deltas.idxmin()]

            position = "test"

        breakpoint()


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

import asyncio
import logging
import os
from datetime import datetime, timedelta
import pandas_market_calendars as mcal

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

import app.database.async_db as async_db
import app.database.models as models
from app.utils import TaskStatusTracker, get_tickers

logger = logging.getLogger(__name__)

THETA_DATA_TERMINAL = os.getenv("THETA_DATA_TERMINAL", "")


class Client:
    def __init__(self, max_concurrent: int = 4):

        # TODO will need to use either a module level client or Redis to ensure concurrency limits across workers
        self._semaphore = asyncio.Semaphore(
            max_concurrent
        )  # Standard subscription allows 4 outstanding requests

    async def get(self, endpoint: str, params: dict):
        url = THETA_DATA_TERMINAL + endpoint
        max_attempts = 10
        for attempt in range(max_attempts):
            response = None
            async with self._semaphore:
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.get(url, params=params, timeout=10)
                        response.raise_for_status()

                        return response.json()

                    except Exception:
                        logger.exception("error getting data from thetadata")
                        if response and response.status_code < 500:
                            break

                        await asyncio.sleep(attempt**2)

        return {}


async def get_eod_options_data_async(client: Client, endpoint, ticker, date):
    params = {
        "symbol": f"{ticker}",
        "expiration": "*",
        "strike": "*",
        "right": "both",
        "start_date": f"{date}",
        "end_date": f"{date}",
        "interval": "1d",
        "format": "json",
    }
    response = await client.get(endpoint, params)
    if not response:
        logger.warning(f"no response received for {ticker} at {endpoint} for {date}")
        return

    response = response["response"]
    to_insert = []
    for item in response:
        contract = item["contract"]
        data = item["data"][0]
        row = {
            "ticker": ticker,
            "quote_date": datetime.fromisoformat(data["timestamp"]),
            "expiration": datetime.fromisoformat(contract["expiration"]),
            "strike": contract["strike"],
            "call_put": contract["right"],
            "underlying_price": data["underlying_price"],
            "open": data["open"],
            "high": data["high"],
            "low": data["low"],
            "close": data["close"],
            "volume": data["volume"],
            "bid": data["bid"],
            "ask": data["ask"],
            "delta": data["delta"],
            "gamma": data["gamma"],
            "theta": data["theta"],
            "vega": data["vega"],
            "rho": data["rho"],
            "implied_vol": data["implied_vol"],
            "iv_error": data["iv_error"],
            "d1": data["d1"],
            "d2": data["d2"],
            "color": data["color"],
            "zomma": data["zomma"],
            "speed": data["speed"],
            "epsilon": data["epsilon"],
            "lambda": data["lambda"],
            "vomma": data["vomma"],
            "vera": data["vera"],
            "veta": data["veta"],
            "ultima": data["ultima"],
            "charm": data["charm"],
            "vanna": data["vanna"],
            "dual_delta": data["dual_delta"],
            "dual_gamma": data["dual_gamma"],
        }
        to_insert.append(row)

    stmt = pg_insert(models.td_eod_options).on_conflict_do_nothing()
    async with async_db.AsyncSessionLocal() as session:
        await session.execute(stmt, to_insert)
        await session.commit()

    logger.info(f"Inserted eod options data for {ticker} on {date}")


async def get_eod_options_data(
    tracker: TaskStatusTracker,
    start_date: str,
    end_date: str,
    ticker: str | None = None,
):
    client = Client()
    endpoint = "/v3/option/history/greeks/eod"

    if ticker is None:
        tickers = get_tickers()
    else:
        tickers = [ticker]

    # Only query for days the market is open
    nyse = mcal.get_calendar("NYSE")
    date_range = nyse.valid_days(start_date=start_date, end_date=end_date)

    tracker.update_status_message(
        f"Getting EOD options data for {len(tickers)} tickers from {start_date} to {end_date}"
    )
    tracker.update_progress(0.2)

    tasks = []
    for date in date_range:
        for ticker in tickers:
            tasks.append(
                get_eod_options_data_async(
                    client, endpoint, ticker, date.strftime("%Y-%m-%d")
                )
            )

    tracker.update_progress(0.3)
    try:
        await asyncio.gather(*tasks)
    finally:
        # The engine will be associated with the first coroutine forever without this
        await async_db.engine.dispose()


if __name__ == "__main__":
    client = Client()
    endpoint = "/v3/option/history/greeks/eod"
    ticker = "AAPL"
    date = "2026-02-17"

    asyncio.run(get_eod_options_data_async(client, endpoint, ticker, date))

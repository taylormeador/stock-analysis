import logging

import pandas as pd
import pandas_ta as ta
import yfinance as yf

import app.database.db as db


logger = logging.getLogger(__name__)


def fetch_historical_data(
    ticker: str,
    start_date: str,
    end_date: str,
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    Fetch historical stock data from yfinance with retry logic.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        max_retries: Maximum number of retry attempts

    Returns:
        List of dictionaries with OHLCV data
    """
    import time

    for attempt in range(max_retries):
        try:
            logger.info(
                f"Fetching historical data for {ticker} from {start_date} to {end_date} (attempt {attempt + 1}/{max_retries})"
            )

            # Add delay to avoid rate limiting
            if attempt > 0:
                wait_time = 2**attempt
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)

            df = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                progress=False,
            )

            if df is None or df.empty:
                logger.warning(f"No data returned for {ticker}")
                return pd.DataFrame()

            df["ticker"] = ticker
            df.columns = df.columns.get_level_values(0)

            logger.info(f"Fetched {len(df.index)} historical records for {ticker}")
            return df

        except Exception as e:
            logger.error(
                f"Error fetching historical data for {ticker} (attempt {attempt + 1}/{max_retries}): {str(e)}"
            )
            if attempt == max_retries - 1:
                return pd.DataFrame()

    return pd.DataFrame()


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # EMA and SMA
    lengths = (9, 10, 12, 26, 50, 100, 200)
    for length in lengths:
        column_name = f"ema_{length}"
        df[column_name] = ta.ema(df.Close, length=length)

        column_name = f"sma_{length}"
        df[column_name] = ta.sma(df.Close, length=length)

    # RSI
    df["rsi_14"] = ta.rsi(df.Close, length=14)

    # MACD
    df[["macd_12_26_9", "macdh_12_26_9", "macds_12_26_9"]] = ta.macd(
        df.Close,
        fast=12,
        slow=26,
        signal=9,
    )

    # Bollinger Bands
    df[["bbl_20", "bbm_20", "bbu_20", "bbb_20", "bbp_20"]] = ta.bbands(
        df.Close,
        length=2,
    )

    return df


def load_price_data(df: pd.DataFrame, ticker: str, start_date: str, end_date: str):
    columns = {
        "Open": "open",
        "Close": "close",
        "High": "high",
        "Low": "low",
        "Volume": "volume",
    }
    df = df.rename(columns=columns)
    df["date"] = df.index
    with db.get_connection() as conn:
        # Load the existing indicator data and fill it in this dataframe so that it doesn't get overwritten
        existing_sql = f"""
            SELECT * FROM stock_prices
            WHERE
                ticker = '{ticker}' AND
                date BETWEEN '{start_date}' AND '{end_date}';
        """
        existing = pd.read_sql(existing_sql, conn)
        filled = df.fillna(existing, axis=1)
        filled.to_sql("stock_prices", conn, if_exists="append")
        conn.commit()
    logger.info(f"wrote {len(df.index)} records for {df.ticker.iloc[0]}")

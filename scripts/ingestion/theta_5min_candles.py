"""
Backfill 5-minute stock OHLC candles from ThetaData into partitioned parquet files.

Uses the `thetadata` pip package (gRPC client, no local Java Terminal needed) —
NOT the older `ThetaData-API/thetadata-python` package that launches a local
Terminal process. Requires Python 3.12+.

    pip install thetadata pandas pyarrow

Symbol universe comes from `client.stock_list_symbols()` — ThetaData doesn't
publish a static ticker list, so we ask it directly.

For each symbol, `stock_history_eod()` (no multi-day limit) is used as a cheap
one-call probe to discover that symbol's actual first/last trading date, since
ThetaData doesn't document how far back a given symbol's data goes. The 5-minute
`stock_history_ohlc()` calls (limited to ~1 month per request) are then only
made across that discovered range, so a young symbol doesn't cost the same as
an old one.

Output is written to OUTPUT_DIR (env: THETA_STOCK_DATA_DIR) as a parquet
dataset hive-partitioned by `date`, e.g. `<root>/date=2024-01-02/*.parquet`.
A per-symbol marker file under `<root>/_ingest_state/` makes reruns skip
symbols that already finished, so an interrupted backfill can be resumed.

Usage:
    python scripts/ingestion/theta_5min_candles.py --email you@example.com --password ***
    python scripts/ingestion/theta_5min_candles.py --api-key $THETADATA_API_KEY --tickers AAPL MSFT
    python scripts/ingestion/theta_5min_candles.py --dry-run  # just list the discovered universe
"""

import argparse
import datetime as dt
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import grpc
import pandas as pd
from thetadata import ThetaClient
from thetadata.errors import AuthenticationError, NoDataFoundError

logger = logging.getLogger("theta_5min_candles")

OUTPUT_DIR = Path(os.getenv("THETA_STOCK_DATA_DIR", "/mnt/srv1-hdd2/stock-data"))
STATE_DIR_NAME = "_ingest_state"

INTERVAL = "5m"
CHUNK_DAYS = 28  # stays under ThetaData's ~1-month limit on multi-day OHLC requests
# Cheap: the EOD probe is a single call regardless of range, so default far back
# and let the probe discover each symbol's real first trading date.
DEFAULT_START = dt.date(1990, 1, 1)
MAX_RETRIES = 5


def month_chunks(start: dt.date, end: dt.date, chunk_days: int = CHUNK_DAYS):
    cur = start
    while cur <= end:
        chunk_end = min(cur + dt.timedelta(days=chunk_days - 1), end)
        yield cur, chunk_end
        cur = chunk_end + dt.timedelta(days=1)


def find_timestamp_column(df: pd.DataFrame) -> str:
    for col in df.columns:
        if "date" in col.lower() or "time" in col.lower():
            return col
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
    raise RuntimeError(f"could not find a date/time column in response: {list(df.columns)}")


def call_with_retry(fn, *args, **kwargs):
    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except (NoDataFoundError, AuthenticationError):
            raise
        except grpc.RpcError as e:
            if attempt == MAX_RETRIES:
                raise
            logger.warning(
                "grpc error on %s (attempt %d/%d): %s — retrying in %.1fs",
                getattr(fn, "__name__", fn),
                attempt,
                MAX_RETRIES,
                e,
                delay,
            )
            time.sleep(delay)
            delay *= 2


def get_universe(client: ThetaClient) -> list[str]:
    df = client.stock_list_symbols()
    col = None
    for candidate in ("symbol", "root", "ticker"):
        if candidate in df.columns:
            col = candidate
            break
    if col is None:
        if len(df.columns) == 1:
            col = df.columns[0]
        else:
            raise RuntimeError(
                f"could not identify the symbol column in stock_list_symbols() response: {list(df.columns)}"
            )
    return sorted(set(df[col].dropna().astype(str)))


def write_bars(df: pd.DataFrame, symbol: str, output_dir: Path):
    ts_col = find_timestamp_column(df)
    df = df.rename(columns={ts_col: "bar_time"})
    df["symbol"] = symbol
    df["date"] = pd.to_datetime(df["bar_time"]).dt.strftime("%Y-%m-%d")
    df.to_parquet(output_dir, engine="pyarrow", partition_cols=["date"], index=False)


def process_symbol(
    client: ThetaClient,
    symbol: str,
    start_date: dt.date,
    end_date: dt.date,
    venue: str | None,
    output_dir: Path,
    state_dir: Path,
) -> str:
    marker = state_dir / f"{symbol}.done"
    if marker.exists():
        return "skipped (already done)"

    try:
        eod = call_with_retry(
            client.stock_history_eod, symbol=symbol, start_date=start_date, end_date=end_date
        )
    except NoDataFoundError:
        marker.write_text("no-data")
        return "no data"

    if eod.empty:
        marker.write_text("no-data")
        return "no data"

    date_col = find_timestamp_column(eod)
    dates = pd.to_datetime(eod[date_col]).dt.date
    avail_start, avail_end = dates.min(), dates.max()

    total_rows = 0
    for chunk_start, chunk_end in month_chunks(avail_start, avail_end):
        kwargs = dict(
            symbol=symbol, interval=INTERVAL, start_date=chunk_start, end_date=chunk_end
        )
        if venue:
            kwargs["venue"] = venue
        try:
            bars = call_with_retry(client.stock_history_ohlc, **kwargs)
        except NoDataFoundError:
            continue
        if bars.empty:
            continue
        write_bars(bars, symbol, output_dir)
        total_rows += len(bars)

    marker.write_text(str(total_rows))
    return f"{total_rows} bars ({avail_start} to {avail_end})"


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--email", help="ThetaData account email (or set THETADATA_CREDENTIALS_FILE / creds.txt)")
    parser.add_argument("--password", help="ThetaData account password")
    parser.add_argument("--api-key", help="ThetaData API key (takes precedence over email/password)")
    parser.add_argument(
        "--tickers", nargs="+", help="Restrict to these symbols instead of the full ThetaData universe"
    )
    parser.add_argument("--limit", type=int, help="Only process the first N symbols (for testing)")
    parser.add_argument("--start-date", type=dt.date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end-date", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument(
        "--venue",
        choices=["nqb", "utp_cta"],
        default=None,
        help="Defaults to the client's own default (nqb / Nasdaq Basic) if unset",
    )
    parser.add_argument("--workers", type=int, default=4, help="Concurrent symbols in flight")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--dry-run", action="store_true", help="Only print the discovered symbol universe and exit"
    )
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    state_dir = output_dir / STATE_DIR_NAME
    state_dir.mkdir(parents=True, exist_ok=True)

    client = ThetaClient(
        email=args.email, password=args.password, api_key=args.api_key, dataframe_type="pandas"
    )

    if args.tickers:
        symbols = args.tickers
    else:
        symbols = get_universe(client)
        logger.info("discovered %d symbols from stock_list_symbols()", len(symbols))

    if args.limit:
        symbols = symbols[: args.limit]

    if args.dry_run:
        for symbol in symbols:
            print(symbol)
        return

    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                process_symbol,
                client,
                symbol,
                args.start_date,
                args.end_date,
                args.venue,
                output_dir,
                state_dir,
            ): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            completed += 1
            try:
                result = future.result()
                logger.info("[%d/%d] %s: %s", completed, len(symbols), symbol, result)
            except Exception:
                logger.exception("[%d/%d] %s failed", completed, len(symbols), symbol)


if __name__ == "__main__":
    main()

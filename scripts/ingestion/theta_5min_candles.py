"""
Backfill 5-minute stock OHLC candles from ThetaData into parquet files.

Uses the `thetadata` pip package (gRPC client, no local Java Terminal needed) —
NOT the older `ThetaData-API/thetadata-python` package that launches a local
Terminal process. Requires Python 3.12+.

    pip install thetadata pandas pyarrow python-dotenv

Symbol universe comes from `client.stock_list_symbols()` — ThetaData doesn't
publish a static ticker list, so we ask it directly.

5-minute bars come from `stock_history_ohlc()`, chunked into ~28-day requests
(ThetaData rejects multi-day requests over ~1 month). A chunk with no data,
or one that falls outside the account's entitled history depth, is skipped
rather than retried — both are permanent, not transient.

Output layout is the resumability mechanism: one file per (symbol, chunk) at
a deterministic path, `<OUTPUT_DIR>/<symbol>/<chunk_start>_<chunk_end>.parquet`.
Before fetching a chunk, its target file's existence is checked — if it's
there, the chunk is skipped. Each file is written to a `.tmp` path and
atomically renamed into place, so a crash mid-write never leaves a partial
file that looks done. There is no separate marker/state directory that can
drift out of sync with what's actually on disk: the data *is* the marker.
This makes the whole backfill idempotent — kill it any time, rerun the exact
same command, and it resumes from wherever it actually left off.

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

INTERVAL = "5m"
CHUNK_DAYS = 28  # stays under ThetaData's ~1-month limit on multi-day OHLC requests
# PERMISSION_DENIED is returned outright (not truncated) for ranges older than
# the account's entitled history depth. Default to a 4-year lookback to match
# a standard-tier account; raise via --start-date if your subscription covers more.
DEFAULT_START = dt.date.today() - dt.timedelta(days=365 * 4)
MAX_RETRIES = 5
# Errors that are permanent for a given request — retrying with the same
# arguments can't change the outcome, so they're not retried.
PERMANENT_ERROR_CODES = (grpc.StatusCode.PERMISSION_DENIED, grpc.StatusCode.INVALID_ARGUMENT)


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
            if e.code() in PERMANENT_ERROR_CODES:
                raise
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


def chunk_path(output_dir: Path, symbol: str, chunk_start: dt.date, chunk_end: dt.date) -> Path:
    # Some symbols (e.g. when-issued securities like ".PR.S/WI") contain "/",
    # which would otherwise be read as a path separator here.
    safe_symbol = symbol.replace("/", "_")
    return output_dir / safe_symbol / f"{chunk_start.isoformat()}_{chunk_end.isoformat()}.parquet"


def write_bars(df: pd.DataFrame, symbol: str, path: Path):
    ts_col = find_timestamp_column(df)
    df = df.rename(columns={ts_col: "bar_time"})
    df["symbol"] = symbol
    df["date"] = pd.to_datetime(df["bar_time"]).dt.strftime("%Y-%m-%d")

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp.parquet")
    df.to_parquet(tmp_path, engine="pyarrow", index=False)
    os.replace(tmp_path, path)  # atomic on the same filesystem


def process_symbol(
    client: ThetaClient,
    symbol: str,
    start_date: dt.date,
    end_date: dt.date,
    venue: str | None,
    output_dir: Path,
) -> str:
    chunks = list(month_chunks(start_date, end_date))
    new_rows = 0
    already_done = 0

    for i, (chunk_start, chunk_end) in enumerate(chunks, start=1):
        path = chunk_path(output_dir, symbol, chunk_start, chunk_end)
        if path.exists():
            already_done += 1
            continue

        kwargs = dict(
            symbol=symbol, interval=INTERVAL, start_date=chunk_start, end_date=chunk_end
        )
        if venue:
            kwargs["venue"] = venue
        try:
            bars = call_with_retry(client.stock_history_ohlc, **kwargs)
        except NoDataFoundError:
            pass
        except grpc.RpcError as e:
            if e.code() not in PERMANENT_ERROR_CODES:
                raise
            logger.warning(
                "%s: chunk %s to %s permanently skipped (%s: %s)",
                symbol, chunk_start, chunk_end, e.code().name, e.details(),
            )
        else:
            if not bars.empty:
                write_bars(bars, symbol, path)
                new_rows += len(bars)

        if i % 5 == 0 or i == len(chunks):
            logger.info(
                "%s: chunk %d/%d done (%s to %s), %d new rows so far (%d chunks already had data)",
                symbol, i, len(chunks), chunk_start, chunk_end, new_rows, already_done,
            )

    return f"{new_rows} new bars, {already_done}/{len(chunks)} chunks already done ({start_date} to {end_date})"


def parse_args():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--email", default=os.getenv("THETADATA_EMAIL"), help="ThetaData account email (or set THETADATA_EMAIL)"
    )
    parser.add_argument(
        "--password",
        default=os.getenv("THETADATA_PASSWORD"),
        help="ThetaData account password (or set THETADATA_PASSWORD)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("THETADATA_API_KEY"),
        help="ThetaData API key (or set THETADATA_API_KEY; takes precedence over email/password)",
    )
    parser.add_argument(
        "--tickers", nargs="+", help="Restrict to these symbols instead of the full ThetaData universe"
    )
    parser.add_argument("--limit", type=int, help="Only process the first N symbols (for testing)")
    parser.add_argument("--start-date", type=dt.date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end-date", type=dt.date.fromisoformat, default=dt.date.today())
    parser.add_argument(
        "--venue",
        choices=["nqb", "utp_cta"],
        default="utp_cta",
        help="utp_cta (consolidated SIP feed) is the default since standard accounts "
        "get INVALID_ARGUMENT on nqb (Nasdaq Basic) — tested empirically.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Concurrent symbols in flight. ThetaData returns RESOURCE_EXHAUSTED above ~3-4 "
        "concurrent requests on standard accounts — tested empirically, not documented.",
    )
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

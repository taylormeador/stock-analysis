import yfinance as yf
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta
import os

# --- Config ---
STOCK_ANALYSIS_DB = os.getenv('STOCK_ANALYSIS_DB')

FUTURES = {
    "ES=F":  "/ES  - S&P 500",
    "MES=F":  "/MES  - Micro S&P 500",
    "GC=F":  "/GC  - Gold",
    "MGC=F": "/MGC - Micro Gold",
    "CL=F":  "/CL  - Crude Oil",
    "MCL=F": "/MCL - Micro Crude Oil",
    "ZN=F":  "/ZN  - 10-Year Treasury",
    "ZC=F":  "/ZC  - Corn",
    "ZW=F":  "/ZW  - Wheat",
    "SI=F":  "/SI  - Silver",
    "NG=F":  "/NG  - Natural Gas",
    "BTC=F": "/BTC - Bitcoin (proxy for /MBT)",
}

end_date   = datetime.today()
start_date = end_date - timedelta(days=365)


def fetch(symbol: str) -> pd.DataFrame:
    df = yf.download(
        symbol,
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        print(f"  No data returned for {symbol}")
        return pd.DataFrame()

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index.name = "date"
    df.reset_index(inplace=True)
    df["symbol"] = symbol
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def upsert(conn, rows: list[tuple]) -> None:
    sql = """
        INSERT INTO futures_prices (symbol, date, open, high, low, close, volume)
        VALUES %s
        ON CONFLICT (symbol, date) DO UPDATE SET
            open   = EXCLUDED.open,
            high   = EXCLUDED.high,
            low    = EXCLUDED.low,
            close  = EXCLUDED.close,
            volume = EXCLUDED.volume
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()


def main():
    conn = psycopg2.connect(STOCK_ANALYSIS_DB)
    print(f"Pulling {start_date.date()} → {end_date.date()}\n")

    for symbol, label in FUTURES.items():
        print(f"Fetching {label} ({symbol})...")
        df = fetch(symbol)
        if df.empty:
            continue

        rows = [
            (
                row.symbol,
                row.date,
                float(row.open)   if pd.notna(row.open)   else None,
                float(row.high)   if pd.notna(row.high)   else None,
                float(row.low)    if pd.notna(row.low)    else None,
                float(row.close),
                int(row.volume)   if pd.notna(row.volume) else None,
            )
            for row in df.itertuples()
        ]

        upsert(conn, rows)
        print(f"  Upserted {len(rows)} rows")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
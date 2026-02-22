import io
import json
import os
import re
from datetime import datetime, timezone

import psycopg2
import zstandard as zstd
from psycopg2.extras import execute_values

SUBREDDITS = {"wallstreetbets"}
BATCH_SIZE = 1000
STOCK_ANALYSIS_DB = os.getenv("STOCK_ANALYSIS_DB")

TICKERS = {
    # Mega caps
    "AAPL",
    "MSFT",
    "GOOGL",
    "GOOG",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "BRK.B",
    "AVGO",
    "LLY",
    "JPM",
    "UNH",
    "V",
    "XOM",
    "MA",
    "JNJ",
    "PG",
    "HD",
    "COST",
    # Large caps
    "NFLX",
    "BAC",
    "ABBV",
    "CRM",
    "CVX",
    "KO",
    "MRK",
    "ORCL",
    "WMT",
    "PEP",
    "TMO",
    "AMD",
    "ACN",
    "CSCO",
    "ADBE",
    "MCD",
    "ABT",
    "DHR",
    "DIS",
    "TXN",
    "INTC",
    "NKE",
    "QCOM",
    "VZ",
    "CMCSA",
    "COP",
    "WFC",
    "PM",
    "AMGN",
    "UNP",
    # Tech & Growth
    "COIN",
    "SQ",
    "PLTR",
    "SNAP",
    "UBER",
    "LYFT",
    "RBLX",
    "CRWD",
    "SNOW",
    "NET",
    "DDOG",
    "ZS",
    "OKTA",
    "TWLO",
    "SHOP",
    "MELI",
    "SE",
    "PYPL",
    "ADYEN",
    "AFRM",
    "RDDT",
    # Meme stocks / WSB favorites
    "GME",
    "AMC",
    "BB",
    "BBBY",
    "WISH",
    "CLOV",
    "SPCE",
    "RIVN",
    "LCID",
    "NIO",
    # Financials
    "GS",
    "MS",
    "C",
    "BLK",
    "SCHW",
    "AXP",
    "HOOD",
    "SOFI",
    "UPST",
    "AFRM",
    # Crypto
    "BTC",
    "ETH",
    "MSTR",
    "IBIT",
    # Aerospace & Defense
    "BA",
    "LMT",
    "RTX",
    "NOC",
    "GD",
    "RKLB",
    "SPCE",
    "ASTS",
    # Biotech / Healthcare
    "MRNA",
    "BNTX",
    "PFE",
    "GILD",
    "REGN",
    "VRTX",
    "BIIB",
    # Data / AI
    "NBIS",
    "CRWV",
    "IREN",
    # ETFs (commonly discussed)
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "VTI",
    "VOO",
    "ARKK",
    "SQQQ",
    "TQQQ",
    "UVXY",
    # Commodities
    "SLV",
    "GLD",
    "COPX",
    "NG",
    "WTI",
    "USO",
    "CL",
    # Energy
    "UUUU",
    "NLR",
    "OKLO",
    "SMR",
}


conn = psycopg2.connect(STOCK_ANALYSIS_DB)


def extract_ticker(text: str):
    """Returns single ticker or None"""
    if not text:
        return

    words = set(re.findall(r"\b[A-Z]{2,5}\b", text.upper()))
    found_tickers = words & TICKERS

    if len(found_tickers) == 1:
        return found_tickers.pop()

    return None


sql = """
    INSERT INTO historical_reddit_posts
        (post_id, subreddit, score, title, body, ticker, author, num_comments, created_utc)
    VALUES %s
    ON CONFLICT DO NOTHING;
"""
template = "(%s, %s, %s, %s, %s, %s, %s, %s, %s)"

batch = []
with open("/mnt/srv2-storage/reddit/reddit/submissions/RS_2025-12.zst", "rb") as fh:
    dctx = zstd.ZstdDecompressor()
    with dctx.stream_reader(fh) as reader:
        text_stream = io.TextIOWrapper(reader, encoding="utf-8")
        i = 0
        for line in text_stream:
            try:
                ln = json.loads(line)  # noqa: E741
                if ln.get("subreddit", "").lower() in SUBREDDITS:
                    created_utc = datetime.fromtimestamp(
                        ln["created_utc"],
                        tz=timezone.utc,
                    )

                    post = (
                        ln.get("id"),
                        ln["subreddit"],
                        ln["score"],
                        ln["title"],
                        ln.get("selftext"),
                        extract_ticker(ln.get("selftext")),
                        ln["author"],
                        ln["num_comments"],
                        created_utc,
                    )
                    batch.append(post)

                    # Bulk insert to DB
                    if len(batch) >= BATCH_SIZE:
                        with conn.cursor() as cur:
                            execute_values(cur, sql, batch, template)
                            conn.commit()
                        batch = []
                        print("inserted batch")

                if i % 100000 == 0:
                    print(f"Processed {i:,} lines")

            except json.JSONDecodeError:
                continue

            except Exception as e:
                print(e)
                breakpoint()

            i += 1

        if batch:
            with conn.cursor() as cur:
                execute_values(cur, sql, batch, template)
                conn.commit()
                print("inserted final partial batch")

        print("ETL complete")

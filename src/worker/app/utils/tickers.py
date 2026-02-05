import os
import app.database.models as models
import app.database.db as db


DATABASE_URL = os.environ["STOCK_ANALYSIS_DB"]

tickers_table = models.tickers


def get_tickers():
    """Gets all tracked tickers"""
    stmt = tickers_table.select().where(tickers_table.c.is_tracked)
    with db.get_connection() as conn:
        results = conn.execute(stmt)
        rows = results.fetchall()

    tickers = [row[1] for row in rows]
    return tickers


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

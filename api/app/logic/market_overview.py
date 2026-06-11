"""
Macro market overview: prices, news, and economic calendar.
Each function is Redis-cached independently at different TTLs.
"""
import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone

import httpx
import pandas as pd
import redis
import yfinance as yf

logger = logging.getLogger(__name__)

_rc = redis.Redis.from_url(os.environ["REDIS_URL"])

# ── Symbols ───────────────────────────────────────────────────────────────────

# 4×4 grid — each group fills one row
SYMBOLS = [
    {"symbol": "^GSPC",    "label": "SPX",    "group": "US Indices & FX"},
    {"symbol": "^NDX",     "label": "NDX",    "group": "US Indices & FX"},
    {"symbol": "^VIX",     "label": "VIX",    "group": "US Indices & FX"},
    {"symbol": "DX-Y.NYB", "label": "DXY",    "group": "US Indices & FX"},
    {"symbol": "ZN=F",     "label": "ZN",     "group": "Rates & Metals"},
    {"symbol": "ZB=F",     "label": "ZB",     "group": "Rates & Metals"},
    {"symbol": "GC=F",     "label": "GC",     "group": "Rates & Metals"},
    {"symbol": "SI=F",     "label": "SI",     "group": "Rates & Metals"},
    {"symbol": "HG=F",     "label": "HG",     "group": "Commodities & Crypto"},
    {"symbol": "CL=F",     "label": "CL",     "group": "Commodities & Crypto"},
    {"symbol": "BTC-USD",  "label": "BTC",    "group": "Commodities & Crypto"},
    {"symbol": "ZC=F",     "label": "ZC",     "group": "Commodities & Crypto"},
    {"symbol": "^N225",    "label": "Nikkei", "group": "International"},
    {"symbol": "^KS11",    "label": "KOSPI",  "group": "International"},
    {"symbol": "^GDAXI",   "label": "DAX",    "group": "International"},
    {"symbol": "^HSI",     "label": "HSI",    "group": "International"},
]

# ── Calendar constants ────────────────────────────────────────────────────────

# FOMC decision dates — published by the Fed a year in advance
_FOMC_DATES = [
    "2026-06-18", "2026-07-29", "2026-09-16",
    "2026-10-28", "2026-12-09",
    "2027-01-27", "2027-03-17", "2027-04-28",
    "2027-06-16", "2027-07-28", "2027-09-15",
    "2027-10-27", "2027-12-08",
]

# FRED release IDs for key macro series
_FRED_RELEASES = [
    (10,  "CPI"),
    (54,  "PCE"),
    (50,  "NFP"),
    (30,  "PPI"),
    (53,  "GDP"),
    (56,  "Retail Sales"),
]

# Companies whose earnings move the broad market or signal macro health
_EARNINGS_WATCHLIST = [
    # Mag 7
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    # Financials
    "JPM", "GS", "BAC", "MS", "BLK", "V", "MA",
    # Consumer
    "WMT", "COST", "HD", "NKE",
    # Industrials / Defense
    "CAT", "BA", "GE", "LMT", "RTX",
    # Healthcare / Pharma
    "UNH", "LLY", "JNJ", "PFE",
    # Energy
    "XOM", "CVX", "COP",
    # Semiconductors
    "AMD", "AVGO", "INTC",
    # Media / Other
    "NFLX", "DIS", "CRM", "BRK-B",
]


# ── Price data ────────────────────────────────────────────────────────────────

def _fetch_prices() -> dict:
    sym_list = [s["symbol"] for s in SYMBOLS]
    try:
        daily  = yf.download(sym_list, period="5d", interval="1d", progress=False, auto_adjust=True, threads=False)
        hourly = yf.download(sym_list, period="5d", interval="1h", progress=False, auto_adjust=True, threads=False)
    except Exception:
        logger.exception("yfinance batch download failed")
        return {"symbols": [], "fetched_at": datetime.now(timezone.utc).isoformat()}

    try:
        d_close = daily["Close"]
        h_close = hourly["Close"]
    except Exception:
        logger.exception("Unexpected yfinance response structure")
        return {"symbols": [], "fetched_at": datetime.now(timezone.utc).isoformat()}

    results = []
    for sym_info in SYMBOLS:
        sym = sym_info["symbol"]
        empty = {**sym_info, "last_price": None, "prev_close": None, "change_pct": None, "chart": []}
        try:
            d_series = d_close[sym].dropna() if sym in d_close.columns else pd.Series(dtype=float)
            h_series = h_close[sym].dropna() if sym in h_close.columns else pd.Series(dtype=float)

            if len(d_series) < 2 or h_series.empty:
                results.append(empty)
                continue

            prev_close    = float(d_series.iloc[-2])
            current_price = float(h_series.iloc[-1])
            change_pct    = round((current_price - prev_close) / prev_close * 100, 2) if prev_close else None

            chart = [
                {"t": pd.Timestamp(ts).isoformat(), "c": round(float(c), 4)}
                for ts, c in h_series.items()
            ]
            results.append({
                **sym_info,
                "last_price": round(current_price, 4),
                "prev_close": round(prev_close, 4),
                "change_pct": change_pct,
                "chart": chart,
            })
        except Exception:
            logger.exception(f"Failed to process {sym}")
            results.append(empty)

    return {"symbols": results, "fetched_at": datetime.now(timezone.utc).isoformat()}


def get_market_overview() -> dict:
    try:
        cached = _rc.get("market:overview")
        if cached:
            return json.loads(cached)
    except Exception:
        logger.warning("Redis read failed for market:overview")

    data = _fetch_prices()
    try:
        _rc.set("market:overview", json.dumps(data), ex=55)  # 55s — stays fresh for 1-min poll
    except Exception:
        logger.warning("Redis write failed for market:overview")
    return data


# ── News ──────────────────────────────────────────────────────────────────────

def get_news() -> list:
    try:
        cached = _rc.get("market:news")
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    api_key = os.environ.get("BENZINGA_API_KEY")
    if not api_key:
        logger.warning("BENZINGA_API_KEY not set — news unavailable")
        return []

    try:
        resp = httpx.get(
            "https://api.benzinga.com/api/v2/news",
            params={"token": api_key, "pageSize": 12, "importance": 3},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        articles = resp.json()
        news = [
            {
                "title": a.get("title", ""),
                "created": a.get("created", ""),
                "url": a.get("url", ""),
                "importance": a.get("importance", 0),
            }
            for a in (articles if isinstance(articles, list) else [])
            if a.get("title")
        ]
        try:
            _rc.set("market:news", json.dumps(news), ex=600)  # 10 min
        except Exception:
            pass
        return news
    except Exception:
        logger.exception("Benzinga news fetch failed")
        return []


# ── Calendar ──────────────────────────────────────────────────────────────────

async def _fetch_one_earnings(sym: str, start: date, end: date) -> dict | None:
    def _sync():
        try:
            df = yf.Ticker(sym).earnings_dates
            if df is None or df.empty:
                return None
            future = [idx.date() for idx in df.index if start <= idx.date() <= end]
            if future:
                return {"date": min(future).isoformat(), "event": f"{sym} Earnings", "category": "earnings"}
        except Exception:
            logger.debug(f"Could not get earnings date for {sym}")
        return None
    return await asyncio.to_thread(_sync)


async def get_calendar() -> list:
    try:
        cached = _rc.get("market:calendar")
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    today = date.today()
    events: list[dict] = []

    # FOMC dates
    for d_str in _FOMC_DATES:
        if date.fromisoformat(d_str) >= today:
            events.append({"date": d_str, "event": "FOMC Decision", "category": "fomc"})

    # FRED releases — async HTTP
    api_key = os.environ.get("FRED_API_KEY")
    if api_key:
        async with httpx.AsyncClient() as client:
            for release_id, name in _FRED_RELEASES:
                try:
                    resp = await client.get(
                        "https://api.stlouisfed.org/fred/release/dates",
                        params={
                            "release_id": release_id,
                            "api_key": api_key,
                            "file_type": "json",
                            "include_release_dates_with_no_data": "true",
                            "sort_order": "desc",
                            "limit": 6,
                        },
                        timeout=10,
                    )
                    resp.raise_for_status()
                    future_dates = sorted([
                        rd["date"] for rd in resp.json().get("release_dates", [])
                        if rd["date"] >= today.isoformat()
                    ])
                    if future_dates:
                        events.append({"date": future_dates[0], "event": name, "category": "macro"})
                except Exception:
                    logger.warning(f"FRED calendar fetch failed for {name} (id={release_id})")

    # Earnings — bounded concurrency so we don't exhaust the thread pool.
    # asyncio.to_thread uses the default executor; cap at 8 simultaneous calls.
    end_date = today + timedelta(days=45)
    sem = asyncio.Semaphore(8)

    async def _limited(sym: str):
        async with sem:
            return await _fetch_one_earnings(sym, today, end_date)

    earnings_results = await asyncio.gather(
        *[_limited(sym) for sym in _EARNINGS_WATCHLIST],
        return_exceptions=False,
    )
    events.extend(e for e in earnings_results if e is not None)

    events.sort(key=lambda x: x["date"])

    try:
        _rc.set("market:calendar", json.dumps(events), ex=21600)  # 6 hr
    except Exception:
        pass
    return events

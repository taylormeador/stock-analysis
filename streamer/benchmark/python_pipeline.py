#!/usr/bin/env python3
"""
Python asyncio options pipeline — benchmark baseline for the Rust streamer.

On startup, discovers all SPX/SPXW option contracts via the ThetaData REST API,
then connects to the WebSocket terminal and subscribes to trade streams for every
contract. Each incoming trade is processed through BSM IV inversion, vol surface
update, and anomaly detection. Latency metrics are published to Redis every second.

Usage:
    REDIS_URL=redis://10.0.10.127:6379/0 python python_pipeline.py [--spx-level 5582]
"""

import argparse
import asyncio
import json
import math
import os
import time
from collections import deque
from datetime import date, datetime, timezone
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv
import httpx
import redis
import websockets

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Configuration ──────────────────────────────────────────────────────────────

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
THETA_HTTP: str = os.getenv("THETA_DATA_HTTP", "")
THETA_WS: str = os.getenv("THETA_DATA_WS", "")
SPX_ROOTS = ["SPX", "SPXW"]
RISK_FREE_RATE: float = 0.053
PUBLISH_INTERVAL: float = 1.0
STATS_INTERVAL: float = 5.0
LATENCY_WINDOW: int = 10_000
QUEUE_MAXSIZE: int = 10_000
MAX_SUBSCRIPTIONS: int = 10_000

ATM_BAND = 0.01  # strikes within 1% of SPX level are treated as ATM


# ── BSM ────────────────────────────────────────────────────────────────────────


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bsm_price(
    S: float, K: float, T: float, r: float, sigma: float, is_call: bool
) -> float:
    if T <= 0 or sigma <= 0:
        return max(0.0, (S - K) if is_call else (K - S))
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    if is_call:
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _bsm_vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return S * math.sqrt(T) * math.exp(-0.5 * d1 * d1) / math.sqrt(2.0 * math.pi)


def bsm_iv(
    S: float, K: float, T: float, r: float, price: float, is_call: bool
) -> float:
    """Newton-Raphson BSM IV inversion. Pure Python — this is the hot path."""
    sigma = 0.2
    for _ in range(50):
        p = _bsm_price(S, K, T, r, sigma, is_call)
        vega = _bsm_vega(S, K, T, r, sigma)
        if abs(vega) < 1e-12:
            break
        sigma -= (p - price) / vega
        sigma = max(0.001, min(sigma, 5.0))
        if abs(_bsm_price(S, K, T, r, sigma, is_call) - price) < 1e-6:
            break
    return sigma


# ── Message types ──────────────────────────────────────────────────────────────


class Tick(NamedTuple):
    K: float  # strike (dollars)
    T: float  # time to expiry (years)
    expiration: int  # YYYYMMDD
    price: float  # mid quote
    is_call: bool
    t_gen: int  # perf_counter_ns at WebSocket receive


class IVTick(NamedTuple):
    iv: float
    K: float
    T: float
    expiration: int
    t_gen: int
    t_bsm: int  # perf_counter_ns after BSM inversion


# ── Shared mutable state (safe: single-threaded asyncio) ──────────────────────

# surface[expiration][strike] = iv
_surface: dict[int, dict[float, float]] = {}
# T for each expiration — updated on every tick, used for calendar spread check
_expiry_T: dict[int, float] = {}
# rolling ATM IV history per expiration for z-score detection
_atm_history: dict[int, deque] = {}

bsm_latencies: deque = deque(maxlen=LATENCY_WINDOW)
pipeline_latencies: deque = deque(maxlen=LATENCY_WINDOW)
anomaly_log: deque = deque(maxlen=200)
ticks_received: int = 0
ticks_processed: int = 0
_spx_level: float = 5_582.0


# ── Contract discovery ─────────────────────────────────────────────────────────


def _fetch_contracts(http_base: str) -> list[dict]:
    """Fetch all active SPX/SPXW option contracts from the list contracts endpoint.

    Response is streamed CSV: "SPX","2026-03-20",6475.000,"CALL"
    Converted to subscription format: {root, expiration (YYYYMMDD int), strike (1/10th cent int), right (C/P)}
    """
    import csv
    import io

    contracts = []
    with httpx.Client(timeout=60.0) as client:
        for root in SPX_ROOTS:
            url = f"{http_base}/v3/option/list/contracts/quote?symbol={root}&date=20250428"  # dev server replays 4/28/25
            print(f"[pipeline] fetching {root} contracts ...", end="", flush=True)
            count = 0
            while url:
                with client.stream("GET", url, timeout=60) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        for row in csv.reader(io.StringIO(line)):
                            if len(row) != 4:
                                continue
                            root_val, exp_str, strike_str, right_str = row
                            if root_val not in SPX_ROOTS:
                                continue
                            try:
                                contracts.append(
                                    {
                                        "root": root_val,
                                        "expiration": int(exp_str.replace("-", "")),
                                        "strike": round(float(strike_str) * 1000),
                                        "right": "C"
                                        if right_str.upper() == "CALL"
                                        else "P",
                                    }
                                )
                                count += 1
                            except (ValueError, KeyError):
                                pass
                    next_page = resp.headers.get("Next-Page")
                    url = next_page if next_page and next_page != "null" else None
            print(f" {count:,}")
    return contracts


# ── Anomaly detection ──────────────────────────────────────────────────────────


def _check_anomalies(iv: float, K: float, T: float, expiration: int) -> list[dict]:
    detected = []
    dte = round(T * 365)

    # 1. ATM IV z-score: flag if ATM IV for this expiry deviates > 2.5σ from rolling mean
    if abs(K - _spx_level) / _spx_level <= ATM_BAND:
        hist = _atm_history.setdefault(expiration, deque(maxlen=100))
        hist.append(iv)
        if len(hist) >= 20:
            mean = sum(hist) / len(hist)
            std = math.sqrt(sum((x - mean) ** 2 for x in hist) / len(hist))
            if std > 1e-6:
                z = (iv - mean) / std
                if abs(z) > 2.5:
                    detected.append(
                        {
                            "type": "IV spike",
                            "strike": K,
                            "dte": dte,
                            "value": round(iv, 4),
                            "threshold": round(mean + 2.5 * std, 4),
                            "detail": f"z={z:.2f}",
                        }
                    )

    # 2. Calendar spread violation: total variance (IV²×T) must be non-decreasing across expiries
    # Build ATM IV per expiry from the nearest-ATM strike we have for each expiration
    atm_points = []
    for exp, strikes in _surface.items():
        T_exp = _expiry_T.get(exp)
        if T_exp is None or T_exp <= 0:
            continue
        nearest_K = min(strikes, key=lambda k: abs(k - _spx_level))
        if abs(nearest_K - _spx_level) / _spx_level <= ATM_BAND * 3:
            atm_points.append((T_exp, strikes[nearest_K], exp))
    atm_points.sort()
    for i in range(1, len(atm_points)):
        T_prev, iv_prev, _ = atm_points[i - 1]
        T_curr, iv_curr, exp_curr = atm_points[i]
        if iv_curr**2 * T_curr < iv_prev**2 * T_prev - 1e-5:
            detected.append(
                {
                    "type": "Calendar spread violation",
                    "strike": _spx_level,
                    "dte": round(T_curr * 365),
                    "value": round(iv_curr**2 * T_curr, 6),
                    "threshold": round(iv_prev**2 * T_prev, 6),
                    "detail": f"{round(T_prev * 365)}D→{round(T_curr * 365)}D total var inverted",
                }
            )
            break

    # 3. Skew inversion: OTM puts should be richer than OTM calls for SPX
    strikes = _surface.get(expiration, {})
    otm_puts = {k: v for k, v in strikes.items() if k <= _spx_level * 0.95}
    otm_calls = {k: v for k, v in strikes.items() if k >= _spx_level * 1.05}
    if otm_puts and otm_calls:
        put_k = max(otm_puts)  # nearest OTM put
        call_k = min(otm_calls)  # nearest OTM call
        skew = otm_puts[put_k] - otm_calls[call_k]
        if skew < 0:
            detected.append(
                {
                    "type": "Skew inversion",
                    "strike": K,
                    "dte": dte,
                    "value": round(skew, 4),
                    "threshold": 0.0,
                    "detail": f"put_iv={otm_puts[put_k]:.3f} call_iv={otm_calls[call_k]:.3f}",
                }
            )

    return detected


# ── Pipeline stages ────────────────────────────────────────────────────────────


async def ws_ingester(
    ws_url: str, contracts: list[dict], iv_queue: asyncio.Queue
) -> None:
    """Connect to ThetaData WebSocket, subscribe to all contracts, feed quotes into queue."""
    global ticks_received
    async for ws in websockets.connect(ws_url):
        try:
            print(
                f"[pipeline] connected — subscribing to {len(contracts):,} contracts ..."
            )
            for i, c in enumerate(contracts):
                await ws.send(
                    json.dumps(
                        {
                            "msg_type": "STREAM",
                            "sec_type": "OPTION",
                            "req_type": "QUOTE",
                            "add": True,
                            "id": i + 1,
                            "contract": c,
                        }
                    )
                )
            print("[pipeline] subscriptions sent — listening for quotes")

            async for message in ws:
                t_recv = time.perf_counter_ns()
                msg = json.loads(message)
                if msg.get("header", {}).get("type") != "QUOTE":
                    continue
                quote = msg.get("quote", {})
                contract = msg.get("contract", {})
                bid = quote.get("bid", 0.0)
                ask = quote.get("ask", 0.0)
                if bid <= 0 or ask <= 0:
                    continue
                mid = (bid + ask) / 2.0
                K = contract.get("strike", 0) / 1000.0
                exp = contract.get("expiration", 0)
                right = contract.get("right", "C")
                quote_date_int = quote.get("date", 0)
                if K <= 0 or exp == 0 or quote_date_int == 0:
                    continue
                exp_date = date(exp // 10000, (exp % 10000) // 100, exp % 100)
                quote_date = date(
                    quote_date_int // 10000,
                    (quote_date_int % 10000) // 100,
                    quote_date_int % 100,
                )
                dte = max(0, (exp_date - quote_date).days)
                T = dte / 365.0
                if T <= 0:
                    continue
                await iv_queue.put(Tick(K, T, exp, mid, right == "C", t_recv))
                ticks_received += 1

        except websockets.ConnectionClosed:
            print("[pipeline] disconnected, reconnecting ...")
            await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            try:
                await ws.send(json.dumps({"msg_type": "STOP"}))
                print("[pipeline] sent STOP, closing connection")
            except Exception:
                pass
            raise


async def iv_calculator(iv_queue: asyncio.Queue, surface_queue: asyncio.Queue) -> None:
    while True:
        tick: Tick = await iv_queue.get()
        iv = bsm_iv(
            _spx_level, tick.K, tick.T, RISK_FREE_RATE, tick.price, tick.is_call
        )
        t_bsm = time.perf_counter_ns()
        bsm_latencies.append(t_bsm - tick.t_gen)
        await surface_queue.put(
            IVTick(iv, tick.K, tick.T, tick.expiration, tick.t_gen, t_bsm)
        )
        iv_queue.task_done()


async def surface_and_anomaly(surface_queue: asyncio.Queue) -> None:
    global ticks_processed
    while True:
        iv_tick: IVTick = await surface_queue.get()
        _surface.setdefault(iv_tick.expiration, {})[iv_tick.K] = iv_tick.iv
        _expiry_T[iv_tick.expiration] = iv_tick.T
        anomalies = _check_anomalies(
            iv_tick.iv, iv_tick.K, iv_tick.T, iv_tick.expiration
        )
        t_done = time.perf_counter_ns()
        pipeline_latencies.append(t_done - iv_tick.t_gen)
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        for a in anomalies:
            a["time"] = now_str
            anomaly_log.appendleft(a)
        ticks_processed += 1
        surface_queue.task_done()


# ── Stats and publishing ───────────────────────────────────────────────────────


def _pct(samples: deque, p: float) -> float:
    if len(samples) < 2:
        return 0.0
    arr = sorted(samples)
    idx = max(0, min(int(len(arr) * p / 100), len(arr) - 1))
    return arr[idx] / 1_000.0


_last_processed: int = 0
_last_stats_time: float = 0.0


async def publisher(
    rc: redis.Redis, iv_queue: asyncio.Queue, surface_queue: asyncio.Queue
) -> None:
    while True:
        await asyncio.sleep(PUBLISH_INTERVAL)
        try:
            if _surface:
                sorted_exps = sorted(_surface.keys())
                all_strikes = sorted(
                    {k for strikes in _surface.values() for k in strikes}
                )
                today = date.today()
                expiries_dte = [
                    max(0, (date(e // 10000, (e % 10000) // 100, e % 100) - today).days)
                    for e in sorted_exps
                ]
                iv_grid = [
                    [_surface[exp].get(k, 0.0) for k in all_strikes]
                    for exp in sorted_exps
                ]
                surface_payload = json.dumps(
                    {
                        "strikes": all_strikes,
                        "expiries_dte": expiries_dte,
                        "iv_grid": iv_grid,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
            else:
                surface_payload = json.dumps(
                    {
                        "strikes": [],
                        "expiries_dte": [],
                        "iv_grid": [],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
            anomalies_payload = json.dumps(list(anomaly_log))
            metrics_payload = json.dumps(
                {
                    "ticks_received": ticks_received,
                    "ticks_processed": ticks_processed,
                    "lag": ticks_received - ticks_processed,
                    "iv_queue_depth": iv_queue.qsize(),
                    "surface_queue_depth": surface_queue.qsize(),
                    "bsm_p50_us": round(_pct(bsm_latencies, 50), 1),
                    "bsm_p99_us": round(_pct(bsm_latencies, 99), 1),
                    "bsm_p999_us": round(_pct(bsm_latencies, 99.9), 1),
                    "pipeline_p50_us": round(_pct(pipeline_latencies, 50), 1),
                    "pipeline_p99_us": round(_pct(pipeline_latencies, 99), 1),
                    "pipeline_p999_us": round(_pct(pipeline_latencies, 99.9), 1),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            await asyncio.to_thread(rc.set, "options:vol_surface", surface_payload)
            await asyncio.to_thread(rc.set, "options:anomalies", anomalies_payload)
            await asyncio.to_thread(rc.set, "options:pipeline_metrics", metrics_payload)
        except Exception as exc:
            print(f"[publisher] Redis error: {exc}")


async def stats_printer(iv_queue: asyncio.Queue, surface_queue: asyncio.Queue) -> None:
    global _last_processed, _last_stats_time
    _last_stats_time = time.perf_counter()
    while True:
        await asyncio.sleep(STATS_INTERVAL)
        now = time.perf_counter()
        elapsed = now - _last_stats_time
        rate = (ticks_processed - _last_processed) / elapsed if elapsed > 0 else 0.0
        _last_processed = ticks_processed
        _last_stats_time = now
        print(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
            f"{rate:,.0f} ticks/sec | recv={ticks_received:,} proc={ticks_processed:,} "
            f"lag={ticks_received - ticks_processed:,} | "
            f"BSM p50={_pct(bsm_latencies, 50):.0f}μs p99={_pct(bsm_latencies, 99):.0f}μs | "
            f"pipeline p99={_pct(pipeline_latencies, 99):.0f}μs p999={_pct(pipeline_latencies, 99.9):.0f}μs"
        )


# ── Entry point ────────────────────────────────────────────────────────────────


async def main() -> None:
    global _spx_level

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spx-level",
        type=float,
        default=5_582.0,
        help="SPX spot level for BSM (use the day's open for dev mode replays)",
    )
    parser.add_argument("--http", default=THETA_HTTP, help="ThetaData HTTP base URL")
    parser.add_argument("--ws", default=THETA_WS, help="ThetaData WebSocket base URL")
    args = parser.parse_args()
    _spx_level = args.spx_level

    print("Python options pipeline starting")
    print(f"  ThetaData HTTP : {args.http}")
    print(f"  ThetaData WS   : {args.ws}")
    print(f"  SPX level      : {_spx_level:,.1f}")
    print(f"  Redis          : {REDIS_URL}")
    print()

    contracts = _fetch_contracts(args.http)
    print(f"[pipeline] {len(contracts):,} total contracts")
    if len(contracts) > MAX_SUBSCRIPTIONS:
        contracts = contracts[:MAX_SUBSCRIPTIONS]
        print(f"[pipeline] capped to {MAX_SUBSCRIPTIONS:,} subscriptions")
    print()

    rc = redis.Redis.from_url(REDIS_URL)
    iv_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    surface_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)

    tasks = asyncio.gather(
        ws_ingester(f"{args.ws}/v1/events", contracts, iv_queue),
        iv_calculator(iv_queue, surface_queue),
        surface_and_anomaly(surface_queue),
        publisher(rc, iv_queue, surface_queue),
        stats_printer(iv_queue, surface_queue),
    )
    try:
        await tasks
    except asyncio.CancelledError:
        tasks.cancel()
        await asyncio.gather(tasks, return_exceptions=True)
        print("[pipeline] shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

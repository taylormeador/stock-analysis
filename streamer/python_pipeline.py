#!/usr/bin/env python3
"""
Python asyncio options pipeline — benchmark baseline for the Rust streamer.

Generates synthetic SPX option ticks at a configurable rate, computes IV via
BSM Newton-Raphson (pure Python, no scipy), builds the 31×9 vol surface,
runs anomaly detection, and publishes results to Redis.

Usage:
    TICK_RATE=5000 REDIS_URL=redis://10.0.10.127:6379/0 python python_pipeline.py

Each "tick" is one contract update: (strike, expiry) → synthetic price → BSM inversion
→ surface cell update → anomaly check. The total pipeline latency per tick
(t_generated → t_anomaly_done) is the number to beat with the Rust pipeline.
"""

import asyncio
import json
import math
import os
import random
import time
from collections import deque
from datetime import datetime, timezone
from typing import NamedTuple

import redis

# ── Configuration ──────────────────────────────────────────────────────────────

TICK_RATE: int = int(os.getenv("TICK_RATE", "5000"))
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BATCH_SIZE: int = 50           # ticks per generator loop iteration
PUBLISH_INTERVAL: float = 1.0  # seconds between Redis writes
STATS_INTERVAL: float = 5.0    # seconds between console output
LATENCY_WINDOW: int = 10_000   # rolling sample count for percentile calc
QUEUE_MAXSIZE: int = 5_000

SPX_LEVEL: float = 5_582.0
RISK_FREE_RATE: float = 0.053
STRIKES: list[float] = [float(k) for k in range(4_000, 7_100, 100)]  # 31
EXPIRIES_DTE: list[int] = [2, 7, 14, 21, 30, 45, 60, 90, 180]         # 9
N_STRIKES = len(STRIKES)
N_EXPIRIES = len(EXPIRIES_DTE)


# ── Ground-truth parametric IV model ──────────────────────────────────────────
# Same model as the frontend: backwardated term structure + negative skew + smile.
# Used to generate synthetic prices; the pipeline then inverts them back to IV.

def _true_iv(K: float, dte: int) -> float:
    base = 0.14 + 0.08 * math.exp(-dte / 30)
    lm = math.log(K / SPX_LEVEL)
    return max(0.02, base * (1 - 0.15 * lm + 0.12 * lm**2))


# Pre-compute for the generator so it doesn't redo this every tick
TRUE_IVS: list[list[float]] = [
    [_true_iv(K, dte) for K in STRIKES] for dte in EXPIRIES_DTE
]


# ── BSM ────────────────────────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bsm_price(S: float, K: float, T: float, r: float, sigma: float, is_call: bool) -> float:
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


def bsm_iv(S: float, K: float, T: float, r: float, price: float, is_call: bool) -> float:
    """Newton-Raphson BSM IV inversion. Pure Python — this is the hot path."""
    sigma = 0.2  # initial guess
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
    strike: float
    dte: int
    si: int           # strike index
    ei: int           # expiry index
    price: float
    is_call: bool
    t_gen: int        # perf_counter_ns at generation


class IVTick(NamedTuple):
    si: int
    ei: int
    iv: float
    t_gen: int
    t_bsm: int        # perf_counter_ns after BSM inversion


# ── Shared mutable state (safe: single-threaded asyncio) ──────────────────────

surface: list[list[float]] = [row[:] for row in TRUE_IVS]  # live IV grid

# Per-expiry rolling ATM IV history for z-score anomaly detection
_ATM_IDX: int = min(range(N_STRIKES), key=lambda i: abs(STRIKES[i] - SPX_LEVEL))
atm_history: list[deque] = [deque(maxlen=100) for _ in range(N_EXPIRIES)]

bsm_latencies: deque = deque(maxlen=LATENCY_WINDOW)       # ns: BSM done - generated
pipeline_latencies: deque = deque(maxlen=LATENCY_WINDOW)   # ns: anomaly done - generated

anomaly_log: deque = deque(maxlen=200)
ticks_generated: int = 0
ticks_processed: int = 0


# ── Anomaly detection ──────────────────────────────────────────────────────────

def _check_anomalies(ei: int, si: int) -> list[dict]:
    detected = []
    row = surface[ei]
    dte = EXPIRIES_DTE[ei]

    # 1. ATM IV z-score: flag if ATM IV deviates > 2.5σ from rolling mean
    atm_iv = row[_ATM_IDX]
    hist = atm_history[ei]
    hist.append(atm_iv)
    if len(hist) >= 20:
        mean = sum(hist) / len(hist)
        variance = sum((x - mean) ** 2 for x in hist) / len(hist)
        std = math.sqrt(variance) if variance > 0 else 0.0
        if std > 1e-6:
            z = (atm_iv - mean) / std
            if abs(z) > 2.5:
                detected.append({
                    "type": "IV spike",
                    "strike": SPX_LEVEL,
                    "dte": dte,
                    "value": round(atm_iv, 4),
                    "threshold": round(mean + 2.5 * std, 4),
                    "detail": f"z={z:.2f}",
                })

    # 2. Calendar spread violation: total variance (IV²×T) must be monotone increasing
    T_vals = [d / 365.0 for d in EXPIRIES_DTE]
    for i in range(1, N_EXPIRIES):
        tv_prev = surface[i - 1][_ATM_IDX] ** 2 * T_vals[i - 1]
        tv_curr = surface[i][_ATM_IDX] ** 2 * T_vals[i]
        if tv_curr < tv_prev - 1e-5:
            detected.append({
                "type": "Calendar spread violation",
                "strike": SPX_LEVEL,
                "dte": EXPIRIES_DTE[i],
                "value": round(tv_curr, 6),
                "threshold": round(tv_prev, 6),
                "detail": f"{EXPIRIES_DTE[i-1]}D→{EXPIRIES_DTE[i]}D total var inverted",
            })
            break  # one per tick is enough

    # 3. Skew shift: OTM-put IV minus OTM-call IV for this expiry
    # Use quartile strikes as put/call proxies
    put_iv = row[N_STRIKES // 4]
    call_iv = row[3 * N_STRIKES // 4]
    skew = put_iv - call_iv
    if skew < 0:  # calls richer than puts — genuine skew inversion for SPX
        detected.append({
            "type": "Skew inversion",
            "strike": STRIKES[si],
            "dte": dte,
            "value": round(skew, 4),
            "threshold": 0.0,
            "detail": f"put_iv={put_iv:.3f} call_iv={call_iv:.3f}",
        })

    return detected


# ── Pipeline stages ────────────────────────────────────────────────────────────

async def generator(iv_queue: asyncio.Queue) -> None:
    """Fire synthetic option ticks at TICK_RATE/sec using batch pacing."""
    global ticks_generated
    interval = BATCH_SIZE / TICK_RATE

    while True:
        t_loop = time.perf_counter()

        for _ in range(BATCH_SIZE):
            si = random.randrange(N_STRIKES)
            ei = random.randrange(N_EXPIRIES)
            K = STRIKES[si]
            dte = EXPIRIES_DTE[ei]
            T = dte / 365.0
            true_sigma = TRUE_IVS[ei][si]
            is_call = K >= SPX_LEVEL

            clean_price = _bsm_price(SPX_LEVEL, K, T, RISK_FREE_RATE, true_sigma, is_call)
            noisy_price = max(0.001, clean_price * (1 + random.gauss(0, 0.005)))

            await iv_queue.put(Tick(K, dte, si, ei, noisy_price, is_call, time.perf_counter_ns()))
            ticks_generated += 1

        elapsed = time.perf_counter() - t_loop
        sleep = interval - elapsed
        if sleep > 0:
            await asyncio.sleep(sleep)


async def iv_calculator(iv_queue: asyncio.Queue, surface_queue: asyncio.Queue) -> None:
    """Invert BSM for each tick. This is the CPU bottleneck in Python."""
    while True:
        tick: Tick = await iv_queue.get()
        T = tick.dte / 365.0
        iv = bsm_iv(SPX_LEVEL, tick.strike, T, RISK_FREE_RATE, tick.price, tick.is_call)
        t_bsm = time.perf_counter_ns()
        bsm_latencies.append(t_bsm - tick.t_gen)
        await surface_queue.put(IVTick(tick.si, tick.ei, iv, tick.t_gen, t_bsm))
        iv_queue.task_done()


async def surface_and_anomaly(surface_queue: asyncio.Queue) -> None:
    """Update the surface cell, run anomaly checks, record total pipeline latency."""
    global ticks_processed
    while True:
        iv_tick: IVTick = await surface_queue.get()
        surface[iv_tick.ei][iv_tick.si] = iv_tick.iv
        anomalies = _check_anomalies(iv_tick.ei, iv_tick.si)
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
    """Return p-th percentile of nanosecond samples, in microseconds."""
    if len(samples) < 2:
        return 0.0
    arr = sorted(samples)
    idx = max(0, min(int(len(arr) * p / 100), len(arr) - 1))
    return arr[idx] / 1_000.0


async def publisher(rc: redis.Redis, iv_queue: asyncio.Queue, surface_queue: asyncio.Queue) -> None:
    """Write surface, anomalies, and metrics to Redis every PUBLISH_INTERVAL seconds."""
    while True:
        await asyncio.sleep(PUBLISH_INTERVAL)
        try:
            surface_payload = json.dumps({
                "strikes": STRIKES,
                "expiries_dte": EXPIRIES_DTE,
                "iv_grid": [row[:] for row in surface],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            anomalies_payload = json.dumps(list(anomaly_log))
            metrics_payload = json.dumps({
                "tick_rate_target": TICK_RATE,
                "ticks_generated": ticks_generated,
                "ticks_processed": ticks_processed,
                "lag": ticks_generated - ticks_processed,
                "iv_queue_depth": iv_queue.qsize(),
                "surface_queue_depth": surface_queue.qsize(),
                "bsm_p50_us": round(_pct(bsm_latencies, 50), 1),
                "bsm_p99_us": round(_pct(bsm_latencies, 99), 1),
                "bsm_p999_us": round(_pct(bsm_latencies, 99.9), 1),
                "pipeline_p50_us": round(_pct(pipeline_latencies, 50), 1),
                "pipeline_p99_us": round(_pct(pipeline_latencies, 99), 1),
                "pipeline_p999_us": round(_pct(pipeline_latencies, 99.9), 1),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await asyncio.to_thread(rc.set, "options:vol_surface", surface_payload)
            await asyncio.to_thread(rc.set, "options:anomalies", anomalies_payload)
            await asyncio.to_thread(rc.set, "options:pipeline_metrics", metrics_payload)
        except Exception as exc:
            print(f"[publisher] Redis error: {exc}")


async def stats_printer(iv_queue: asyncio.Queue, surface_queue: asyncio.Queue) -> None:
    """Print pipeline health to stdout every STATS_INTERVAL seconds."""
    while True:
        await asyncio.sleep(STATS_INTERVAL)
        lag = ticks_generated - ticks_processed
        print(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
            f"rate={TICK_RATE}/s | gen={ticks_generated:,} | proc={ticks_processed:,} | lag={lag:,} | "
            f"iv_q={iv_queue.qsize()} surf_q={surface_queue.qsize()} | "
            f"BSM p50={_pct(bsm_latencies, 50):.0f}μs p99={_pct(bsm_latencies, 99):.0f}μs | "
            f"pipeline p99={_pct(pipeline_latencies, 99):.0f}μs p999={_pct(pipeline_latencies, 99.9):.0f}μs"
        )


# ── Entry point ────────────────────────────────────────────────────────────────

async def main() -> None:
    rc = redis.Redis.from_url(REDIS_URL)
    iv_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    surface_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)

    print(f"Python options pipeline starting")
    print(f"  TICK_RATE : {TICK_RATE:,}/sec")
    print(f"  Surface   : {N_STRIKES} strikes × {N_EXPIRIES} expiries = {N_STRIKES * N_EXPIRIES} contracts")
    print(f"  Redis     : {REDIS_URL}")
    print(f"  BSM work  : ~{TICK_RATE * 50} Newton-Raphson iterations/sec")
    print()

    await asyncio.gather(
        generator(iv_queue),
        iv_calculator(iv_queue, surface_queue),
        surface_and_anomaly(surface_queue),
        publisher(rc, iv_queue, surface_queue),
        stats_printer(iv_queue, surface_queue),
    )


if __name__ == "__main__":
    asyncio.run(main())

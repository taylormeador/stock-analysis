#!/usr/bin/env python3
"""
Deterministic tick server — drop-in WebSocket replacement for ThetaData.

Emits synthetic SPX option ticks at a configurable rate. The pipeline connects
here instead of ThetaData so benchmarks are reproducible and source-independent.

Usage:
    python tick_server.py --tick-rate 5000 --port 25521 [--seed 42]
"""

import argparse
import asyncio
import json
import math
import random
import time

import websockets

# ── Surface config (must match python_pipeline.py) ────────────────────────────

SPX_LEVEL = 5_582.0
RISK_FREE_RATE = 0.053
STRIKES: list[float] = [float(k) for k in range(4_000, 7_100, 100)]
EXPIRIES_DTE: list[int] = [2, 7, 14, 21, 30, 45, 60, 90, 180]
N_STRIKES = len(STRIKES)
N_EXPIRIES = len(EXPIRIES_DTE)
BATCH_SIZE = 50


def _true_iv(K: float, dte: int) -> float:
    base = 0.14 + 0.08 * math.exp(-dte / 30)
    lm = math.log(K / SPX_LEVEL)
    return max(0.02, base * (1 - 0.15 * lm + 0.12 * lm**2))


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


TRUE_IVS: list[list[float]] = [
    [_true_iv(K, dte) for K in STRIKES] for dte in EXPIRIES_DTE
]


async def _handle(ws, tick_rate: int, seed: int) -> None:
    rng = random.Random(seed)
    interval = BATCH_SIZE / tick_rate
    addr = ws.remote_address
    print(f"[tick_server] {addr} connected — {tick_rate:,} ticks/sec")
    try:
        while True:
            t_loop = time.perf_counter()
            batch = []
            for _ in range(BATCH_SIZE):
                si = rng.randrange(N_STRIKES)
                ei = rng.randrange(N_EXPIRIES)
                K = STRIKES[si]
                dte = EXPIRIES_DTE[ei]
                T = dte / 365.0
                true_sigma = TRUE_IVS[ei][si]
                is_call = K >= SPX_LEVEL
                clean_price = _bsm_price(SPX_LEVEL, K, T, RISK_FREE_RATE, true_sigma, is_call)
                noisy_price = max(0.001, clean_price * (1 + rng.gauss(0, 0.005)))
                batch.append({
                    "si": si, "ei": ei,
                    "strike": K, "dte": dte,
                    "price": noisy_price,
                    "is_call": is_call,
                    "t_gen": time.perf_counter_ns(),
                })
            await ws.send(json.dumps(batch))
            elapsed = time.perf_counter() - t_loop
            sleep = interval - elapsed
            if sleep > 0:
                await asyncio.sleep(sleep)
    except websockets.ConnectionClosed:
        print(f"[tick_server] {addr} disconnected")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tick-rate", type=int, default=5_000)
    parser.add_argument("--port", type=int, default=25521)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"[tick_server] ws://localhost:{args.port}  rate={args.tick_rate:,}/sec  seed={args.seed}")

    async with websockets.serve(
        lambda ws: _handle(ws, args.tick_rate, args.seed),
        "localhost", args.port,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

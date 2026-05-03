#!/usr/bin/env python3
"""
Benchmark harness — passive observer that measures a running pipeline.

Start the pipeline (and ThetaData dev mode for Rust builds) before running this.
The harness waits for warmup to pass, snapshots metrics at the start of the
measurement window, waits for the window to close, then computes throughput and
logs the result to Postgres.

Usage:
    REDIS_URL=redis://... STOCK_ANALYSIS_DB=postgresql://... \
        python bench.py --version-tag "python-asyncio-v1" [--duration 60] [--warmup 10]
"""

import argparse
import json
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import psycopg2
import redis

REDIS_URL = os.getenv("REDIS_URL", "")
DB_URL = os.getenv("STOCK_ANALYSIS_DB", "")


def _wait_for_pipeline(rc: redis.Redis, timeout: int = 30) -> None:
    """Block until pipeline_metrics appears in Redis."""
    print("[bench] waiting for pipeline ...", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if rc.exists("options:pipeline_metrics"):
            print(" ready")
            return
        print(".", end="", flush=True)
        time.sleep(1.0)
    raise SystemExit(
        f"\n[bench] pipeline did not appear in Redis within {timeout}s — is it running?"
    )


def _read(rc: redis.Redis) -> dict:
    raw = rc.get("options:pipeline_metrics")
    if not raw:
        raise SystemExit("[bench] pipeline metrics disappeared mid-run")
    return json.loads(raw)


def _countdown(seconds: int, label: str) -> None:
    for i in range(seconds):
        remaining = seconds - i
        if remaining % 10 == 0 or remaining <= 3:
            print(f"[bench] {label}: {remaining}s remaining")
        time.sleep(1.0)


def _write_result(
    run_id: str,
    args: argparse.Namespace,
    metrics: dict,
    start_snap: dict,
    end_snap: dict,
) -> None:
    ticks_in_window = end_snap["ticks_processed"] - start_snap["ticks_processed"]
    throughput = ticks_in_window / args.duration
    metrics["observed_throughput_per_s"] = round(throughput, 1)

    print()
    print(f"[bench] ── results ──────────────────────────────────────────────")
    print(f"[bench] run_id          : {run_id}")
    print(f"[bench] version_tag     : {args.version_tag}")
    print(
        f"[bench] ticks processed : {ticks_in_window:,}  ({throughput:,.0f} ticks/sec)"
    )
    print(
        f"[bench] BSM      p50 / p99 / p999 : "
        f"{metrics['bsm_p50_us']} / {metrics['bsm_p99_us']} / {metrics['bsm_p999_us']} μs"
    )
    print(
        f"[bench] pipeline p50 / p99 / p999 : "
        f"{metrics['pipeline_p50_us']} / {metrics['pipeline_p99_us']} / {metrics['pipeline_p999_us']} μs"
    )

    if not DB_URL:
        print("[bench] STOCK_ANALYSIS_DB not set — skipping DB write")
        return

    conn = psycopg2.connect(DB_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO benchmark_runs
                        (run_id, version_tag, warmup_s, duration_s,
                         ticks_processed, metrics)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id,
                        args.version_tag,
                        args.warmup,
                        args.duration,
                        ticks_in_window,
                        json.dumps(metrics),
                    ),
                )
        print(f"[bench] logged to DB")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version-tag",
        required=True,
        help='e.g. "python-asyncio-v1", "rust-spsc-rayon-v1"',
    )
    parser.add_argument(
        "--duration", type=int, default=60, help="Measurement window in seconds"
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=10,
        help="Warmup seconds to wait before measurement starts",
    )
    args = parser.parse_args()

    run_id = str(uuid.uuid4())
    rc = redis.Redis.from_url(REDIS_URL)

    print(f"[bench] run_id      : {run_id}")
    print(f"[bench] version_tag : {args.version_tag}")
    print(f"[bench] warmup={args.warmup}s  measurement={args.duration}s")
    print()

    _wait_for_pipeline(rc)
    _countdown(args.warmup, "warmup")
    print("[bench] warmup done — starting measurement window")

    start_snap = _read(rc)
    _countdown(args.duration, "measuring")
    end_snap = _read(rc)

    # Latency percentiles are rolling windows; the end snapshot reflects steady state.
    metrics = {
        k: end_snap[k]
        for k in (
            "bsm_p50_us",
            "bsm_p99_us",
            "bsm_p999_us",
            "pipeline_p50_us",
            "pipeline_p99_us",
            "pipeline_p999_us",
        )
        if k in end_snap
    }

    _write_result(run_id, args, metrics, start_snap, end_snap)
    print("[bench] done")


if __name__ == "__main__":
    main()

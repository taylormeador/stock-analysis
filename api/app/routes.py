import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

import app.logic.etl_status as etl_status
import app.logic.options as options
import app.logic.prometheus as prometheus
import app.logic.whats_hot as whats_hot
import app.logic.portfolio_forecasts as portfolio_forecasts
import app.logic.tastytrade as tastytrade_logic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

FLOWER_URL = os.getenv("FLOWER_URL", "")


# ── Request model ─────────────────────────────────────────────────────────────


class StopUpdateRequest(BaseModel):
    stop_amount: float | None = None
    stop_mode: str = "stop_loss"
    notes: str | None = None


class PortfolioCalcRequest(BaseModel):
    start_date: str
    end_date: str
    capital: float
    symbols: list[str] | None = None
    variations: list[str] | None = None
    vol_target_pct: float = 0.20


# ── Existing routes ───────────────────────────────────────────────────────────


@router.get("/home")
async def get_home():
    tasks = [
        whats_hot.get_topic_snapshot(),
        whats_hot.get_ticker_mentions(),
        etl_status.get_etl_task_statuses(),
        prometheus.get_celery_stats(),
    ]
    results = await asyncio.gather(*tasks)
    data = {
        "snapshot": results[0].to_dict("records"),
        "ticker_mentions": results[1].to_dict("records"),
        "etl_task_statuses": results[2].to_dict("records"),
        "celery_stats": results[3],
    }
    logger.info(data)
    return {"data": data}


@router.get("/whats-hot")
async def get_whats_hot():
    logger.info("calculating data for hot dashboard")
    tasks = [
        whats_hot.get_ticker_mentions(),
        whats_hot.get_top_comments(),
        whats_hot.get_topic_snapshots(),
        whats_hot.get_market_data(),
    ]
    results = await asyncio.gather(*tasks)
    data = {
        "ticker_mentions": results[0].to_dict("records"),
        "top_comments": results[1].to_dict("records"),
        "topic_snapshots": [snapshot.to_dict("records") for snapshot in results[2]],
        "market_data": results[3],
    }
    return {"data": data}


@router.get("/etl-status/")
async def get_etl_status():
    tasks = [
        etl_status.get_etl_task_statuses(),
        etl_status.get_failed_task_count(),
        etl_status.get_task_time_deltas(),
        prometheus.get_tasks_processed_last_24h(),
        prometheus.get_task_failure_rate(),
    ]
    results = await asyncio.gather(*tasks)
    data = {
        "etl_task_statuses": results[0].to_dict("records"),
        "failed_task_count": results[1].to_dict("records"),
        "task_time_deltas": results[2].to_dict("records"),
        "num_tasks_processed": results[3],
        "task_failure_rate": results[4],
    }
    return {"data": data}


# ── Portfolio routes ──────────────────────────────────────────────────────────


@router.get("/portfolio/variations")
async def get_portfolio_variations():
    """Active trading rule variations from the DB."""
    data = await portfolio_forecasts.get_variations()
    return {"data": data}


@router.get("/portfolio/runs")
async def get_portfolio_runs():
    """All distinct run_ids in portfolio_calculations."""
    data = await portfolio_forecasts.get_runs()
    return {"data": data}


@router.get("/portfolio/forecasts/{run_id}")
async def get_portfolio_forecasts_endpoint(
    run_id: str,
    lookback_days: int = Query(default=180, ge=1, le=365),
):
    """
    Returns price history, forecast history, and portfolio calculations
    for all active instruments, filtered to the given run_id.
    """
    data = await portfolio_forecasts.get_portfolio_forecasts(lookback_days, run_id)
    return {"data": data}


@router.post("/portfolio/calculate/{run_id}")
async def trigger_portfolio_calculations(
    run_id: str,
    request: PortfolioCalcRequest,
):
    """
    Trigger an ad-hoc portfolio calculation run via Flower.
    Poll ETL Status for progress, then fetch results from
    /portfolio/forecasts/{run_id} once complete.
    """
    payload = {
        "kwargs": {
            "start_date": request.start_date,
            "end_date": request.end_date,
            "run_id": run_id,
            "capital": request.capital,
            "variations": request.variations,
            "symbols": request.symbols,
            "vol_target_pct": request.vol_target_pct,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{FLOWER_URL}/api/task/async-apply/app.tasks.portfolio.run_portfolio_calculations",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        return {
            "data": {
                "task_id": result.get("task-id"),
                "run_id": run_id,
                "status": "submitted",
            }
        }
    except httpx.HTTPError as e:
        logger.exception(f"Failed to submit task via Flower: {e}")
        raise HTTPException(status_code=502, detail=f"Flower request failed: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error submitting task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/vol-surface")
async def get_vol_surface():
    data = await asyncio.to_thread(options.get_vol_surface)
    return {"data": data}


@router.get("/options/anomalies")
async def get_anomalies():
    data = await asyncio.to_thread(options.get_anomalies)
    return {"data": data}


@router.get("/options/benchmark-runs")
async def options_benchmark_runs():
    data = await options.get_benchmark_runs()
    return {"data": data}


@router.get("/options/pipeline-metrics")
async def get_pipeline_metrics():
    data = await asyncio.to_thread(options.get_pipeline_metrics)
    return {"data": data}


# ── Tastytrade routes ─────────────────────────────────────────────────────────


@router.get("/tastytrade/dashboard")
async def get_tastytrade_dashboard():
    """Account balances, positions, and computed risk metrics."""
    data = await tastytrade_logic.get_dashboard()
    return {"data": data}


@router.put("/tastytrade/stops/{account_number}/{symbol:path}")
async def update_position_stop(
    account_number: str,
    symbol: str,
    request: StopUpdateRequest,
):
    """Set or update the stop-loss annotation for a position."""
    await tastytrade_logic.update_stop(
        account_number=account_number,
        symbol=symbol,
        stop_amount=request.stop_amount,
        stop_mode=request.stop_mode,
        notes=request.notes,
    )
    return {"data": {"status": "ok"}}


@router.get("/backtest")
async def get_backtest():
    """TODO"""
    return {"data": None}


@router.get("/celery-stats")
async def get_celery_stats_endpoint():
    stats = await prometheus.get_celery_stats()
    return {"data": stats}


if __name__ == "__main__":
    import asyncio

    asyncio.run(get_etl_status())

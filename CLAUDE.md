# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Multi-service stock analysis platform supporting discretionary trading. Core workflow: scheduled data ingestion → ML analysis → EWMAC forecast generation → dashboard display.

**Trading approach:** Hybrid discretionary — Carver-style EWMAC trend forecasts are used as one signal among several that a human trader weighs. No automated position sizing or order execution. The forecast is a dimensionless trend-strength signal (±20 scale); the trader decides what to do with it.

**Instruments traded:** Equity index futures (/MES, /MNQ, /M2K) and crypto (/MBT), using index/ETF spot prices (^GSPC, QQQ, IWM, GLD, BTC-USD) as proxies for forecast generation. Backadjusted futures data costs money; spot prices are free via yfinance and track the futures closely enough for trend signals. Commodity futures (oil, grains) are excluded because their ETF proxies structurally diverge from futures due to roll yield.

## Services

| Service | Language | Purpose |
|---|---|---|
| `api/` | Python/FastAPI | REST API, async SQLAlchemy |
| `worker/` | Python/Celery | Task queue: scraping, ML, forecasts |
| `streamer/` | Rust/Tokio | WebSocket client for real-time options data |
| `backtester/` | Rust | EWMAC strategy backtesting engine |
| `frontend/streamlit/` | Python/Streamlit | Multi-page dashboard |

## Commands

### Python Services

```bash
# API
docker-compose -f api/docker-compose.yml up

# Workers (CPU, long-running, GPU variants)
docker-compose -f worker/docker-compose.yml --profile worker --profile worker-long --profile worker-gpu up

# Frontend
cd frontend/streamlit/app && streamlit run app.py
```

### Rust Services

```bash
cd streamer && cargo build --release
cd backtester && cargo build --release
```

### Database Setup

```bash
psql stock_analysis_db < database/ddls/ddls.sql
psql stock_analysis_db < database/ddls/reddit_ddls.sql
psql stock_analysis_db < database/ddls/options.sql
psql stock_analysis_db < database/ddls/portfolio.sql
psql stock_analysis_db < database/ddls/add_spot_instruments.sql
```

## Architecture

### Task Distribution

The worker service runs multiple Celery queues:
- **CPU worker** — scraping, API data ingestion, data processing
- **Long worker** — historical data ingestion, large batch jobs  
- **GPU worker** — ML inference (FinBERT sentiment, embeddings, model training)
- **Celery Beat** — schedules all recurring tasks

### Celery Beat Schedule

| Time | Tasks |
|---|---|
| Every 2 min | Scrape WSB daily thread |
| Every 10 min | Scrape top Reddit comments + embeddings |
| Hourly | Futures data (no active instruments currently), price cache update |
| 8:00 AM daily | Stock data (incl. spot instruments), CBOE stats, FRED data, options |
| 8:15 AM daily | Spot vol — EWMA vol for active spot instruments → `instrument_vol` |
| 8:30 AM daily | EWMAC forecasts for all active instruments → `forecasts` |
| 4x daily | LLM summaries via Claude API (premarket, midday, close, evening) |

### Key Patterns

- All Celery tasks use `@track_task_metrics` for Prometheus metrics
- `@SingleInstanceTask` prevents duplicate concurrent task runs
- `TaskStatusTracker` writes ETL progress to `etl_task_status` table
- `DistributedRateLimiter` (Redis-backed) rate-limits external API calls
- API uses async SQLAlchemy; workers use sync SQLAlchemy
- Redis serves as both Celery broker and price/embedding cache
- PostgreSQL uses the pgvector extension for 384-dim sentence embeddings

### Data Pipeline

1. **Ingest** — Reddit (PRAW), yfinance, FRED, CBOE, Theta Data Terminal options
2. **Analyze** — VADER + FinBERT sentiment, sentence-transformer embeddings, BERTopic clustering, LLM summaries (Claude)
3. **Model** — XGBoost/LightGBM forecasting, EWMAC trading rules
4. **Display** — FastAPI serves Streamlit frontend; Flower monitors tasks

Portfolio position sizing (FDM, IDM, capital allocation) is intentionally not run — forecasts are used as discretionary signals, not automated orders.

### Instrument & Price Model

The `instruments` table is the registry of what gets forecasts. Key columns:
- `is_active` — controls whether the instrument runs through the forecast pipeline
- `price_source` — `'stock_prices'` or `'futures_prices'`; tells every query which table to read from

Active instruments are all spot/index (`price_source = 'stock_prices'`):

| symbol | label | asset_class |
|---|---|---|
| `^GSPC` | SPX | equity_index |
| `QQQ` | QQQ | equity_index |
| `IWM` | IWM | equity_index |
| `GLD` | GLD | metals |
| `BTC-USD` | BTC | crypto |

`stock_prices` is the single source of truth for all spot/index price data (OHLCV + technical indicators). `futures_prices` remains intact for actual futures data but has no active instruments currently. The `price_source` indirection means the EWMAC pipeline, API, and vol computation all dispatch to the correct table without hardcoding.

Migration: `database/ddls/add_spot_instruments.sql`

### Streamer Service

The `streamer/` service is a Rust low-latency market data pipeline. Its primary purpose is learning systems programming with real financial data.

**Planned architecture:**
- Single tokio async task owns the WebSocket receive loop (IO-bound — one thread is correct; a WebSocket is a single ordered TCP stream)
- Lock-free SPSC ring buffer hand-off between ingestion and processing threads (implementing from scratch as the core learning artifact)
- Rayon thread pool for CPU-bound work: BSM inversions across the full SPX/SPXW options chain
- Hot path stays in-memory; async fire-and-forget DB/Redis writes on a separate thread

**Output:** Real-time vol surface (strike × expiry grid of IV), anomaly detection (skew inversions, put/call parity violations, term structure breaks, IV spikes), timestamped signal emission.

**Theta Data Terminal connection:**
- Docker container on homelab at `10.0.10.127`
- HTTP REST on port `25503`; WebSocket streaming on port `25520`
- WebSocket endpoint: `ws://10.0.10.127:25520/v1/events` (docs still say v1 even though API is otherwise v3)
- Must send a JSON subscription payload after connecting; send unsubscribe before disconnect
- Use `docker compose down && docker compose up` (not `restart`) to pick up port mapping changes

**Key monitoring metric:** `ss -tn` `Recv-Q` on the WebSocket connection — zero means the receive loop is keeping up. Ring buffer fill % is the next bottleneck to watch.

**Benchmarking system** (`streamer/`) — passive harness for comparing pipeline versions:

- `python_pipeline.py` — asyncio pipeline with a self-saturating internal generator (no external tick source needed). Each tick → BSM Newton-Raphson inversion → surface update → anomaly detection. Records `perf_counter_ns()` at each stage boundary; publishes p50/p99/p999 latencies to Redis every second. For Rust builds, ThetaData dev mode (replay a full day at >real-time speed) is the natural tick source.
- `bench.py` — passive harness: waits for the pipeline to appear in Redis, waits through warmup, snapshots metrics at the start and end of the measurement window, computes throughput from the delta, writes a row to `benchmark_runs`. Does not spawn or manage any processes.
- `tick_server.py` — WebSocket tick server for isolated testing without ThetaData. Not used in the normal bench flow.

Three anomaly detectors: ATM IV z-score per expiry, calendar spread violation (total variance monotonicity), skew inversion (OTM put IV < OTM call IV).

```bash
pip install -r streamer/requirements_pipeline.txt

# Terminal 1: start the pipeline (fetches contracts from REST on startup, then streams trades)
# --spx-level should match the underlying level for the day being replayed in dev mode
REDIS_URL=redis://10.0.10.127:6379/0 python streamer/python_pipeline.py --spx-level 5582

# Terminal 2: run a timed benchmark once pipeline prints "listening for trades"
REDIS_URL=redis://10.0.10.127:6379/0 STOCK_ANALYSIS_DB=postgresql://... \
  python streamer/bench.py --version-tag "python-asyncio-v1" --duration 60 --warmup 10
```

`THETA_DATA_HTTP` and `THETA_DATA_WS` env vars override the default homelab addresses (`10.0.10.127:25510` and `10.0.10.127:25520`).

**API endpoints** (read from Redis, served by FastAPI):
- `GET /api/options/vol-surface`
- `GET /api/options/anomalies`
- `GET /api/options/pipeline-metrics`

**Frontend** at `frontend/streamlit/app/page_modules/options_dashboard.py` — consumes the real API endpoints, refreshing every 5s via `@st.fragment`. Falls back to mock data when the pipeline is not running (shown with 🔴 indicator).

## Environment Variables

```
# Database
STOCK_ANALYSIS_DB=postgresql://user:pass@host/db
ASYNC_STOCK_ANALYSIS_DB=postgresql+asyncpg://user:pass@host/db

# Infrastructure
REDIS_URL=redis://host:6379/0
MLFLOW_TRACKING_URI=http://host:5000
PROMETHEUS_URL=http://host:9090
FLOWER_URL=http://host:5555

# External APIs
FRED_API_KEY=
ANTHROPIC_API_KEY=
BENZINGA_API_KEY=
THETA_DATA_TERMINAL=ws://host:25520  # streamer WebSocket; REST clients use http://host:25503

# Workers
EMBEDDING_BATCH_SIZE=10000
EMBEDDING_NUM_BATCHES=100
SENTIMENT_BATCH_SIZE=10000
SENTIMENT_NUM_BATCHES=100
NODE_ID=
CELERY_METRICS_PORT=9808
FLOWER_UNAUTHENTICATED_API=true
```

## Ports

| Port | Service |
|---|---|
| 8000 | FastAPI |
| 5555 | Flower (task monitoring) |
| 5000 | MLFlow |
| 6379 | Redis |
| 9090 | Prometheus |
| 9808 | Celery exporter metrics |
| 25503/25520 | Theta Data Terminal |

## Networking

All services run on Docker bridge network `stock-analysis-network`. Internal IPs: `10.0.10.121` (DB), `10.0.10.127` (Redis/Prometheus/MLFlow).

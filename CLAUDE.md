# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Multi-service stock analysis and quantitative trading platform. Core workflow: scheduled data ingestion → ML analysis → EWMAC forecast generation → portfolio calculation → dashboard display.

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
| Hourly | Futures data, price cache update |
| 8:00 AM daily | Stock data, CBOE stats, FRED data, options |
| 8:30 AM daily | EWMAC forecasts for all variations |
| 8:45 AM daily | Portfolio calculations (4 futures: /MES, /MBT, /ZC, /MGC) |
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
4. **Portfolio** — Forecast variations → position sizing → backtest verification
5. **Display** — FastAPI serves Streamlit frontend; Flower monitors tasks

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

**Python benchmark pipeline** at `streamer/python_pipeline.py` — asyncio pipeline that is the baseline to beat with the Rust service:
- Generator fires synthetic option ticks at a configurable rate (`TICK_RATE`, default 5000/sec)
- Each tick → BSM Newton-Raphson inversion (pure Python, no scipy) → surface cell update → anomaly detection
- Three anomaly checks: ATM IV z-score per expiry, calendar spread violation (total variance monotonicity), skew inversion
- Records `perf_counter_ns()` timestamps at each stage boundary → publishes real p50/p99/p999 latencies to Redis
- Writes `options:vol_surface`, `options:anomalies`, `options:pipeline_metrics` to Redis every second

Run: `pip install redis && TICK_RATE=5000 REDIS_URL=redis://10.0.10.127:6379/0 python streamer/python_pipeline.py`

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

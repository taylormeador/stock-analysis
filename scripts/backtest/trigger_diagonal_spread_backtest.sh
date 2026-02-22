#!/bin/bash
curl -X POST http://10.0.10.127:5555/api/task/async-apply/app.tasks.backtests.run_pmcc_backtest \
  -H "Content-Type: application/json" \
  -d '{"kwargs": {"ticker": "SPY", "start_date": "2021-01-01", "end_date": "2021-02-01"}}'
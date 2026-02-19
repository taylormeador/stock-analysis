#!/bin/bash
curl -X POST http://10.0.10.127:5555/api/task/async-apply/app.tasks.apis.get_eod_option_data \
  -H "Content-Type: application/json" \
  -d '{"kwargs": {"start_date": "2019-01-01", "end_date": "2019-12-31"}}'
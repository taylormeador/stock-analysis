#!/bin/bash
curl -X POST http://10.0.10.127:5555/api/task/async-apply/app.tasks.apis.get_eod_options_data \
  -H "Content-Type: application/json" \
  -d '{"kwargs": {"start_date": "2016-01-01", "end_date": "2016-12-31"}}'
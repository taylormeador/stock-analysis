#!/bin/bash
# Backfill forecasts and portfolio calculations for a date range.
# Usage: ./backfill_portfolio.sh 2025-01-01 2025-12-31

FLOWER_URL="http://10.0.10.127:5555"
START_DATE="${1:-2025-01-01}"
END_DATE="${2:-$(date +%Y-%m-%d)}"

echo "Backfilling from $START_DATE to $END_DATE"

current="$START_DATE"
while [[ "$current" < "$END_DATE" || "$current" == "$END_DATE" ]]; do
    # Skip weekends
    day_of_week=$(date -d "$current" +%u 2>/dev/null || date -j -f "%Y-%m-%d" "$current" +%u)
    if [[ "$day_of_week" -le 5 ]]; then
        echo "Processing $current..."

        # Fire forecast generation
        curl -s -X POST "$FLOWER_URL/api/task/async-apply/app.tasks.portfolio.generate_ewmac_forecasts" \
            -H "Content-Type: application/json" \
            -d "{\"kwargs\": {\"as_of\": \"$current\"}}" > /dev/null

        # Small delay to avoid hammering the broker
        sleep 0.5

        # Fire portfolio calculations
        curl -s -X POST "$FLOWER_URL/api/task/async-apply/app.tasks.portfolio.run_portfolio_calculations" \
            -H "Content-Type: application/json" \
            -d "{\"kwargs\": {\"as_of\": \"$current\"}}" > /dev/null

        sleep 0.5
    else
        echo "Skipping $current (weekend)"
    fi

    # Increment date — works on both Linux and macOS
    current=$(date -d "$current + 1 day" +%Y-%m-%d 2>/dev/null || date -j -v+1d -f "%Y-%m-%d" "$current" +%Y-%m-%d)
done

echo "Done. Check Flower for task status."
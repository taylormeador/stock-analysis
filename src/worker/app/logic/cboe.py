import requests
from datetime import datetime, timedelta, date, timezone
import logging
import time
from sqlalchemy.dialects.postgresql import insert

import app.database.db as db
from app.database.models import cboe_daily_stats
from app.utils import ETLStatusTracker

logger = logging.getLogger(__name__)


ratio_mapping = {
    "TOTAL PUT/CALL RATIO": "total_put_call_ratio",
    "INDEX PUT/CALL RATIO": "index_put_call_ratio",
    "EQUITY PUT/CALL RATIO": "equity_put_call_ratio",
    "CBOE VOLATILITY INDEX (VIX) PUT/CALL RATIO": "vix_put_call_ratio",
}


def scrape_daily_market_stats(
    tracker: ETLStatusTracker,
    start_date_str: str | None = None,
    end_date_str: str | None = None,
):
    """
    For backfilling, start_date and end_date can be provided.
    Default behavior is to get the data for today only.
    """
    # Compute date range
    date_format = "%Y-%m-%d"
    if start_date_str is None or end_date_str is None:
        start_date_str = date.today().strftime(date_format)
        end_date_str = date.today().strftime(date_format)

    start_date = datetime.strptime(start_date_str, date_format).date()
    end_date = datetime.strptime(end_date_str, date_format).date() + timedelta(days=1)

    date_range = [
        start_date + timedelta(days=x) for x in range(0, (end_date - start_date).days)
    ]
    date_range = [date for date in date_range if date.weekday() < 5]
    if not date_range:
        logger.info("no valid dates for CBOE market stats")
        return

    tracker.update_status_message("Scraping...")
    logger.info(f"starting CBOE scrape for {start_date} to {end_date}")
    scraped_at = datetime.now(timezone.utc)

    all_stats = []
    for target_date in date_range:
        url = f"https://cdn.cboe.com/data/us/options/market_statistics/daily/{target_date}_daily_options"
        logger.info(f"GET {url}")
        response = requests.get(url)
        if not response.ok:
            logger.error(
                f"error getting market data from CBOE: {response.status_code} {response.reason} {response.text}"
            )
            continue

        try:
            daily_stats = {}

            data = response.json()
            for ratio in data["ratios"]:
                daily_stats_key = ratio_mapping.get(ratio["name"])
                if daily_stats_key:
                    daily_stats[daily_stats_key] = ratio["value"]

            rows = data["SUM OF ALL PRODUCTS"]
            daily_stats["total_volume"] = rows[0]["total"]
            daily_stats["total_oi"] = rows[1]["total"]

            daily_stats["date"] = target_date
            daily_stats["scraped_at"] = scraped_at
            all_stats.append(daily_stats)

        except Exception as e:
            logger.error(f"error while scraping CBOE daily stats: {e}")

        time.sleep(0.2)  # be nice to CDN

    # Insert to db, ignoring duplicates
    if all_stats:
        with db.get_connection() as conn:
            stmt = insert(cboe_daily_stats).values(all_stats)
            stmt = stmt.on_conflict_do_nothing(index_elements=["date"])
            conn.execute(stmt)
            conn.commit()

    logger.info(f"inserted {len(all_stats)} cboe daily records")
    tracker.update_status_message(f"Updated {len(all_stats)} CBOE recods")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # scrape_daily_market_stats(start_date_str="2019-01-01", end_date_str="2026-01-01")

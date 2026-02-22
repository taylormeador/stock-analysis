import logging
import os
from datetime import datetime, timezone

import fredapi
import pandas as pd
from sqlalchemy.dialects.postgresql import insert

import app.database.db as db
from app.database.models import fred_macro_data
from app.utils import TaskStatusTracker, Status

logger = logging.getLogger(__name__)

FRED_API_KEY = os.getenv("FRED_API_KEY")
fred = fredapi.Fred(api_key=FRED_API_KEY)


def get_fred_data(tracker: TaskStatusTracker):
    logger.info("hitting FRED API")

    scraped_at = datetime.now(timezone.utc)

    treasury_ten_year = fred.get_series("DGS10")
    tracker.update_progress(0.4, persist=True)
    fed_funds_rate = fred.get_series("DFF")
    tracker.update_progress(0.5, persist=True)
    dollar_index = fred.get_series("DTWEXBGS")
    tracker.update_progress(0.6, persist=True)
    unemployment_rate = fred.get_series("UNRATE")
    tracker.update_progress(0.7, persist=True)

    df = pd.DataFrame(
        {
            "treasury_ten_year": treasury_ten_year,
            "fed_funds_rate": fed_funds_rate,
            "dollar_index": dollar_index,
            "unemployment_rate": unemployment_rate,
            "scraped_at": scraped_at,
        }
    )
    df["date"] = df.index

    stmt = insert(fred_macro_data).values(df.to_dict("records"))
    stmt = stmt.on_conflict_do_update(
        index_elements=["date"],
        set_={
            "treasury_ten_year": stmt.excluded.treasury_ten_year,
            "fed_funds_rate": stmt.excluded.fed_funds_rate,
            "dollar_index": stmt.excluded.dollar_index,
            "unemployment_rate": stmt.excluded.unemployment_rate,
            "scraped_at": stmt.excluded.scraped_at,
        },
    )

    with db.get_connection() as conn:
        conn.execute(stmt)
        conn.commit()

    tracker.update_status_message(f"Updated FRED data {[col for col in df.columns]}")
    logger.info("updated FRED table")


if __name__ == "__main__":
    pass

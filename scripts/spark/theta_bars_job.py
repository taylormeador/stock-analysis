"""
Spark job over the ThetaData 5-minute bar lake (see
scripts/ingestion/theta_5min_candles.py for how it's written: one file per
symbol/chunk at `<data-dir>/<symbol>/<chunk_start>_<chunk_end>.parquet`).

Currently a smoke test only: confirms the NFS-mounted data is readable from
every node in the Spark cluster and reports counts for the given date range.
No real transformation yet — that comes once the cluster + NFS path are
proven to work end to end.

Takes an explicit date range because this same job is meant to be reused for
both the one-off historical backfill (wide range, run by hand) and the
future incremental job (narrow range, run on a schedule) — it's the same
processing either way, just a different range, not two separate jobs.

    docker compose exec spark /opt/spark/bin/spark-submit /opt/jobs/theta_bars_job.py \\
        --data-dir /mnt/srv1-hdd2/stock-data --start-date 2024-01-01 --end-date 2024-01-31
"""

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="e.g. /mnt/srv1-hdd2/stock-data")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD, inclusive")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD, inclusive")
    return parser.parse_args()


def main():
    args = parse_args()
    spark = SparkSession.builder.appName("theta-bars-job").getOrCreate()

    df = (
        spark.read.parquet(f"{args.data_dir}/*/*.parquet")
        .where(F.col("date").between(args.start_date, args.end_date))
    )

    row_count = df.count()
    symbol_count = df.select("symbol").distinct().count()
    print(f"rows in range: {row_count}")
    print(f"distinct symbols: {symbol_count}")
    df.select("symbol", "date").distinct().orderBy("symbol", "date").show(20, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()

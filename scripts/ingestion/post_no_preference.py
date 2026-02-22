import pandas as pd
import os
import sqlalchemy

STOCK_ANALYSIS_DB = os.environ["STOCK_ANALYSIS_DB"]


def get_connection():
    engine = sqlalchemy.create_engine(url=STOCK_ANALYSIS_DB)
    return engine.connect()


def main():
    chunk_size = 10000
    path = "~/Downloads/post-no-preference_options_master_option_chain.csv"
    cols = {"act_symbol": "ticker"}

    with get_connection() as conn:
        with pd.read_csv(path, chunksize=chunk_size) as r:
            for i, chunk in enumerate(r):
                print(f"inserting chunk {i}")
                df = pd.DataFrame(chunk)
                df = df.rename(columns=cols)
                df.to_sql(
                    "post_no_preference_option_chain",
                    conn,
                    if_exists="append",
                    index=False,
                )


if __name__ == "__main__":
    main()

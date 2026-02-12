import pandas as pd
import py7zr
import os
import sqlalchemy
import numpy as np

STOCK_ANALYSIS_DB = os.environ["STOCK_ANALYSIS_DB"]


def get_connection():
    engine = sqlalchemy.create_engine(url=STOCK_ANALYSIS_DB)
    return engine.connect()


def extract_files():
    paths = [
        "/home/taylor/Downloads/spy_eod_2010-bndqqt.7z",
        "/home/taylor/Downloads/spy_eod_2011-vdjy9h.7z",
        "/home/taylor/Downloads/spy_eod_2012-gghtsj.7z",
        "/home/taylor/Downloads/spy_eod_2013-davchg.7z",
        "/home/taylor/Downloads/spy_eod_2014-6rlzuz.7z",
        "/home/taylor/Downloads/spy_eod_2015-2djnnd.7z",
        "/home/taylor/Downloads/spy_eod_2016-6kgvva.7z",
        "/home/taylor/Downloads/spy_eod_2017-owhrwk.7z",
        "/home/taylor/Downloads/spy_eod_2018-7fpgd6.7z",
        "/home/taylor/Downloads/spy_eod_2019-eotnx0.7z",
        "/home/taylor/Downloads/spy_eod_2020-kwe0mi.7z",
        "/home/taylor/Downloads/spy_eod_2021-borwkq.7z",
        "/home/taylor/Downloads/spy_eod_2022q1-ww0cra.7z",
        "/home/taylor/Downloads/spy_eod_2022q2-xofvwa.7z",
        "/home/taylor/Downloads/spy_eod_2022q3-we1um1.7z",
        "/home/taylor/Downloads/spy_eod_2022q4-wh2csq.7z",
        "/home/taylor/Downloads/spy_eod_2023q1-zfoivd.7z",
        "/home/taylor/Downloads/spy_eod_2023q2-nnkjka.7z",
        "/home/taylor/Downloads/spy_eod_2023q3-nyvdmv.7z",
        "/home/taylor/Downloads/spy_eod_2023q4-vzwoxb.7z",
    ]
    for path in paths:
        with py7zr.SevenZipFile(path, mode="r") as ar:
            ar.extractall(path="/home/taylor/Downloads/extractions")


def main():

    keep_cols = [
        " [QUOTE_READTIME]",
        " [UNDERLYING_LAST]",
        " [EXPIRE_DATE]",
        " [DTE]",
        " [C_DELTA]",
        " [C_GAMMA]",
        " [C_VEGA]",
        " [C_THETA]",
        " [C_RHO]",
        " [C_IV]",
        " [C_VOLUME]",
        " [C_LAST]",
        " [C_SIZE]",
        " [C_BID]",
        " [C_ASK]",
        " [STRIKE]",
        " [P_BID]",
        " [P_ASK]",
        " [P_SIZE]",
        " [P_LAST]",
        " [P_DELTA]",
        " [P_GAMMA]",
        " [P_VEGA]",
        " [P_THETA]",
        " [P_RHO]",
        " [P_IV]",
        " [P_VOLUME]",
        " [STRIKE_DISTANCE]",
        " [STRIKE_DISTANCE_PCT]",
    ]

    cols = {
        " [QUOTE_READTIME]": "quote_read_time",
        " [UNDERLYING_LAST]": "underlying_last",
        " [EXPIRE_DATE]": "expire_date",
        " [DTE]": "dte",
        " [C_DELTA]": "c_delta",
        " [C_GAMMA]": "c_gamma",
        " [C_VEGA]": "c_vega",
        " [C_THETA]": "c_theta",
        " [C_RHO]": "c_rho",
        " [C_IV]": "c_iv",
        " [C_VOLUME]": "c_volume",
        " [C_LAST]": "c_last",
        " [C_SIZE]": "c_size",
        " [C_BID]": "c_bid",
        " [C_ASK]": "c_ask",
        " [STRIKE]": "strike",
        " [P_BID]": "p_bid",
        " [P_ASK]": "p_ask",
        " [P_SIZE]": "p_size",
        " [P_LAST]": "p_last",
        " [P_DELTA]": "p_delta",
        " [P_GAMMA]": "p_gamma",
        " [P_VEGA]": "p_vega",
        " [P_THETA]": "p_theta",
        " [P_RHO]": "p_rho",
        " [P_IV]": "p_iv",
        " [P_VOLUME]": "p_volume",
        " [STRIKE_DISTANCE]": "strike_distance",
        " [STRIKE_DISTANCE_PCT]": "strike_distance_pct",
    }

    base_path = "/home/taylor/Downloads/extractions/"
    paths = os.listdir(base_path)
    chunk_size = 10000
    with get_connection() as conn:
        for path in paths:
            print(f"parsing {base_path + path}")
            with pd.read_csv(base_path + path, chunksize=chunk_size) as r:
                for i, chunk in enumerate(r):
                    print(f"inserting chunk {i}")
                    df = pd.DataFrame(chunk)
                    df = df[keep_cols]
                    df = df.rename(columns=cols)

                    # Make datetime aware
                    naive = pd.Series(pd.to_datetime(df.quote_read_time))
                    naive.dt.tz_localize("EST")

                    # Munge
                    df.expire_date = pd.to_datetime(df.expire_date)

                    for col in (
                        "c_volume",
                        "p_volume",
                        "c_iv",
                        "p_iv",
                        "c_delta",
                        "p_delta",
                        "c_gamma",
                        "p_gamma",
                        "c_theta",
                        "p_theta",
                        "c_vega",
                        "p_vega",
                        "c_rho",
                        "p_rho",
                        "c_last",
                        "p_last",
                        "c_bid",
                        "c_ask",
                        "p_bid",
                        "p_ask",
                    ):
                        df.loc[df[col] == " ", col] = np.nan  # TODO interpolate?
                        df[col] = df[col].astype(float)

                    df.p_size = df.p_size.str.strip()
                    df.c_size = df.c_size.str.strip()

                    # I believe this is a data error.
                    # I am solving this by interpolating from the nearest two rows
                    if not df[df.p_gamma < -1000].empty:
                        before = df[df.index == df[df.p_gamma < -1000].index[0] - 1]
                        after = df[df.index == df[df.p_gamma < -1000].index[0] + 1]
                        breakpoint()

                    try:
                        df.to_sql(
                            "spy_eod_options",
                            conn,
                            if_exists="append",
                            index=False,
                        )
                    except Exception as e:
                        import traceback

                        traceback.print_exc()
                        breakpoint()


if __name__ == "__main__":
    main()

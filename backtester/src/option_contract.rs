use crate::DbPool;
use chrono::NaiveDate;

#[derive(Debug, Clone)]
pub struct OptionContract {
    pub ticker: String,
    pub quote_date: NaiveDate,
    pub expiration: NaiveDate,
    pub strike: f64,
    pub bid: f64,
    pub ask: f64,
    pub spread: f64,
    pub mid: f64,
    pub delta: f64,
}

pub fn get_option_contracts(
    pool: &DbPool,
    ticker: &str,
    start_date: NaiveDate,
    end_date: NaiveDate,
) -> Vec<OptionContract> {
    let mut client = pool.get().unwrap();
    let rows = client
        .query(
            "
            SELECT
                ticker,
                quote_date,
                expiration,
                strike::float8,
                bid::float8,
                ask::float8,
                ROUND(ask - bid, 2)::float8 as spread,
                ROUND((ask - bid) / 2 + bid, 2)::float8 as mid,
                delta::float8 
            FROM td_eod_options
            WHERE
                ticker = $1 AND
                call_put = 'CALL' AND
                quote_date BETWEEN $2 AND $3
            ORDER BY quote_date ASC;
        ",
            &[&ticker, &start_date, &end_date],
        )
        .expect("Failed to fetch rows");

    rows.iter()
        .map(|row| OptionContract {
            ticker: row.get("ticker"),
            quote_date: row.get("quote_date"),
            expiration: row.get("expiration"),
            strike: row.get("strike"),
            bid: row.get("bid"),
            ask: row.get("ask"),
            spread: row.get("spread"),
            mid: row.get("mid"),
            delta: row.get("delta"),
        })
        .collect::<Vec<OptionContract>>()
}

use sqlx::postgres::PgPoolOptions;
use chrono::NaiveDate; 
use dotenvy::dotenv;
use std::env;

#[derive(Debug, sqlx::FromRow)]
struct OptionContract {
    ticker: String,
    quote_date: NaiveDate,
    expiration: NaiveDate,
    strike: f64,
    bid: f64,
    ask: f64,
    delta: f64,
}

#[tokio::main]
async fn main() {
    dotenv().ok();

    let database_url = env::var("ASYNC_STOCK_ANALYSIS_DB").expect("ASYNC_STOCK_ANALYSIS_DB must be set");

    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await
        .expect("Failed to connect to database");

    println!("Connected to database");

    let rows = sqlx::query_as::<_, OptionContract>(
        "SELECT ticker, quote_date, expiration, strike, bid, ask, delta 
         FROM td_eod_options
         WHERE ticker = $1 AND call_put = 'CALL'
         LIMIT 10"
    )
    .bind("SPY")
    .fetch_all(&pool)
    .await
    .expect("Failed to fetch rows");

    for row in rows {
        println!("{:?}", row);
    }
}
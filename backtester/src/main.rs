use postgres::{Client, NoTls};
use chrono::NaiveDate;
use dotenvy::dotenv;
use std::env;
use rust_decimal::Decimal;
use std::io;

mod task_status_tracker;
use task_status_tracker::TaskStatusTracker;

mod diagonal_spread;

#[derive(Debug)]
struct OptionContract {
    ticker: String,
    quote_date: NaiveDate,
    expiration: NaiveDate,
    strike: Decimal,
    bid: Decimal,
    ask: Decimal,
    delta: Decimal,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenv().ok();
    

    let database_url = env::var("STOCK_ANALYSIS_DB").expect("STOCK_ANALYSIS_DB must be set");

    let mut client = Client::connect(&database_url, NoTls)
        .expect("Failed to connect to database");

    println!("Connected to database");

    let mut tracker = TaskStatusTracker::new(
        client,
        String::from("test-task-id-3"),
        String::from("Backtest Worker"),
        String::from("Blazingly fast backtests"),
    );


    let ticker= "SPY".to_string();
    let window_start_date = NaiveDate::from_ymd_opt(2021, 1, 1).ok_or("Invalid start date")?;
    let window_end_date = NaiveDate::from_ymd_opt(2021, 1, 1).ok_or("Invalid end date")?;
    diagonal_spread::run_backtest(tracker, ticker, window_start_date, window_end_date);


    // // Read data
    // let rows = client.query(
    //     "SELECT ticker, quote_date, expiration, strike, bid, ask, delta 
    //      FROM td_eod_options
    //      WHERE ticker = $1 AND call_put = 'CALL'
    //      LIMIT 10",
    //     &[&"SPY"],
    // ).expect("Failed to fetch rows");

    // for row in &rows {
    //     let contract = OptionContract {
    //         ticker: row.get("ticker"),
    //         quote_date: row.get("quote_date"),
    //         expiration: row.get("expiration"),
    //         strike: row.get("strike"),
    //         bid: row.get("bid"),
    //         ask: row.get("ask"),
    //         delta: row.get("delta"),
    //     };
    //     println!("{:?}", contract);
    // }

    Ok(())

}
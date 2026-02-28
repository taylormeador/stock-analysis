use postgres::{Client, NoTls};
use chrono::NaiveDate;
use dotenvy::dotenv;
use std::env;

mod task_status_tracker;
use task_status_tracker::TaskStatusTracker;

mod diagonal_spread;
mod option_contract;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::init();
    dotenv().ok();
    log::info!("Test");

    let database_url = env::var("STOCK_ANALYSIS_DB").expect("STOCK_ANALYSIS_DB must be set");

    // TODO use a connection pool;
    let client = Client::connect(&database_url, NoTls)
        .expect("Failed to connect to database");

    println!("Connected to database");

    let mut tracker = TaskStatusTracker::new(
        client,
        String::from("test-task-id-3"),
        String::from("Backtest Worker"),
        String::from("Blazingly fast backtests"),
    );


    let ticker= "SPY";
    let window_start_date = NaiveDate::from_ymd_opt(2021, 1, 1).ok_or("Invalid start date")?;
    let window_end_date = NaiveDate::from_ymd_opt(2021, 1, 5).ok_or("Invalid end date")?;
    
    // Read options data
    let client = Client::connect(&database_url, NoTls)
        .expect("Failed to connect to database");

    println!("Connected to database");

    diagonal_spread::run_backtest(client, tracker, &ticker, window_start_date, window_end_date);


    Ok(())

}
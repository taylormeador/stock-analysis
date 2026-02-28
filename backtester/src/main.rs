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

    let args: Vec<String> = std::env::args().collect();
    if args.len() != 4 {
        return Err("Usage: backtester <ticker> <start_date> <end_date>".into());
    }

    let ticker = &args[1];
    let window_start_date = NaiveDate::parse_from_str(&args[2], "%Y-%m-%d")
        .map_err(|_| "Invalid start date format, expected YYYY-MM-DD")?;
    let window_end_date = NaiveDate::parse_from_str(&args[3], "%Y-%m-%d")
        .map_err(|_| "Invalid end date format, expected YYYY-MM-DD")?;

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
    
    // Read options data
    let client = Client::connect(&database_url, NoTls)
        .expect("Failed to connect to database");

    println!("Connected to database");

    diagonal_spread::run_backtest(client, tracker, &ticker, window_start_date, window_end_date);

    Ok(())

}
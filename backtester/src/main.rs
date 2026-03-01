use chrono::NaiveDate;
use dotenvy::dotenv;
use postgres::NoTls;
use r2d2::Pool;
use r2d2_postgres::PostgresConnectionManager;
use std::env;

mod task_status_tracker;
use task_status_tracker::TaskStatusTracker;

mod strategies;
use strategies::diagonal_spread_param_sweep::run_backtest;

mod option_contract;

type DbPool = Pool<PostgresConnectionManager<NoTls>>;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::init();
    dotenv().ok();

    let args: Vec<String> = std::env::args().collect();
    if args.len() != 5 {
        return Err("Usage: backtester <task_id> <ticker> <start_date> <end_date>".into());
    }

    let task_id = &args[1];
    let ticker = args[2].clone();
    let window_start_date = NaiveDate::parse_from_str(&args[3], "%Y-%m-%d")
        .map_err(|_| "Invalid start date format, expected YYYY-MM-DD")?;
    let window_end_date = NaiveDate::parse_from_str(&args[4], "%Y-%m-%d")
        .map_err(|_| "Invalid end date format, expected YYYY-MM-DD")?;

    let database_url = env::var("STOCK_ANALYSIS_DB").expect("STOCK_ANALYSIS_DB must be set");

    let manager = PostgresConnectionManager::new(database_url.parse()?, NoTls);
    let pool = Pool::new(manager)?;
    println!("Connected to database");

    // We assume that Python called start_task() and update the record it made
    let tracker = TaskStatusTracker::new(
        &pool,
        task_id,
        "Backtest Worker",
        "Blazingly fast backtests",
    );

    run_backtest(&pool, &tracker, ticker, window_start_date, window_end_date);

    tracker.complete_task();

    Ok(())
}

use postgres::{Client, NoTls};
use chrono::{NaiveDate, DateTime, Utc};
use dotenvy::dotenv;
use std::env;
use rust_decimal::Decimal;
use std::fmt;

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

enum TaskStatus {
    InProgress,
    Failed,
    Complete,
}

impl fmt::Display for TaskStatus {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TaskStatus::InProgress => write!(f, "In Progress"),
            TaskStatus::Failed => write!(f, "Failed"),
            TaskStatus::Complete => write!(f, "Complete"),
        }
    }
}


fn main() {
    dotenv().ok();

    let database_url = env::var("STOCK_ANALYSIS_DB").expect("STOCK_ANALYSIS_DB must be set");

    let mut client = Client::connect(&database_url, NoTls)
        .expect("Failed to connect to database");

    println!("Connected to database");

    // Read data
    let rows = client.query(
        "SELECT ticker, quote_date, expiration, strike, bid, ask, delta 
         FROM td_eod_options
         WHERE ticker = $1 AND call_put = 'CALL'
         LIMIT 10",
        &[&"SPY"],
    ).expect("Failed to fetch rows");

    for row in &rows {
        let contract = OptionContract {
            ticker: row.get("ticker"),
            quote_date: row.get("quote_date"),
            expiration: row.get("expiration"),
            strike: row.get("strike"),
            bid: row.get("bid"),
            ask: row.get("ask"),
            delta: row.get("delta"),
        };
        println!("{:?}", contract);
    }

    // Write data
    let task_id = "test-task-id";
    let component_name = "Backtest Worker";
    let task_description = "Blazingly fast backtests";
    let status = TaskStatus::InProgress;
    let status_message = "Rust is tight";
    let progress: f64 = 0.0420;
    let start_time: DateTime<Utc> = Utc::now();

    let sql = "
        INSERT INTO etl_task_status (
            task_id,
            component_name,
            task_description,
            status,
            status_message,
            progress,
            start_time
        ) VALUES ($1, $2, $3, $4, $5, $6, $7);
         ";
    client.execute(sql, &[&task_id, &component_name, &task_description, &status.to_string(), &status_message, &progress, &start_time]).expect("Error writing data to db");

}
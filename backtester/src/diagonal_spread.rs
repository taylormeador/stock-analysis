use chrono::NaiveDate;
use crate::task_status_tracker::TaskStatusTracker;
use crate::OptionContract;
use itertools::iproduct;
use std::fmt;

enum TransactionType {
    BTO,
    STO,
    BTC,
    STC
}

struct ParamGrid {
    long_delta: Vec<f64>,
    long_dte: Vec<i32>,
    long_close_dte: Vec<i32>,
    short_delta: Vec<f64>,
    short_dte: Vec<i32>,
    short_close_delta: Vec<f64>,
    short_close_dte: Vec<i32>,
    short_close_profit: Vec<f64>,
    slippage: Vec<f64>,
    stop_loss: Vec<f64>,
    profit_target: Vec<f64>,
}

struct DiagonalSpreadParams {
    long_delta: f64,
    long_dte: i32,
    long_close_dte: i32,
    short_delta: f64,
    short_dte: i32,
    short_close_delta: f64,
    short_close_dte: i32,
    short_close_profit: f64,
    slippage: f64,
    stop_loss: f64,
    profit_target: f64,
}

impl fmt::Display for DiagonalSpreadParams {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "long_delta={} long_dte={} long_close_dte={} short_delta={} short_dte={} short_close_delta={} short_close_dte={} short_close_profit={} slippage={} self.stop_loss={} self.stop_loss={}",
        self.long_delta, self.long_dte, self.long_close_dte, self.short_delta, self.short_dte,
        self.short_close_delta, self.short_close_dte, self.short_close_profit, self.slippage,
        self.stop_loss, self.profit_target)
    }
}

struct DiagonalSpreadStrategy {
    ticker: String,
    start_date: NaiveDate,
    strategy_params: DiagonalSpreadParams
}

struct DiagonalSpreadPosition {
    long_call: OptionContract,
    short_call: OptionContract,
    stop_loss: f64,
    profit_target: f64,
    slippage: f64
}

pub fn run_backtest(tracker: TaskStatusTracker, ticker: String, window_start_date: NaiveDate, window_end_date: NaiveDate) {
    let param_grid = ParamGrid {
        long_delta: vec![0.9, 0.8, 0.7, 0.6],
        long_dte: vec![180, 270, 365],
        long_close_dte: vec![75, 90, 105, 120],
        short_delta: vec![0.2, 0.3],
        short_dte: vec![28, 35, 42],
        short_close_delta: vec![0.4, 0.5, 0.6],
        short_close_dte: vec![7, 14, 21],
        short_close_profit: vec![0.5, 0.75],
        slippage: vec![0.5, 0.75],
        stop_loss: vec![0.05, 0.1, 0.2, 0.3],
        profit_target: vec![0.25, 0.50, 0.75],
    };
    for (long_delta, long_dte, long_close_dte, short_delta, short_dte, short_close_delta, short_close_dte, short_close_profit, slippage, stop_loss, profit_target) in iproduct!(
    &param_grid.long_delta,
    &param_grid.long_dte,
    &param_grid.long_close_dte,
    &param_grid.short_delta,
    &param_grid.short_dte,
    &param_grid.short_close_delta,
    &param_grid.short_close_dte,
    &param_grid.short_close_profit,
    &param_grid.slippage,
    &param_grid.stop_loss,
    &param_grid.profit_target,
) {
    let strategy_params = DiagonalSpreadParams {
        long_delta: *long_delta,
        long_dte: *long_dte,
        long_close_dte: *long_close_dte,
        short_delta: *short_delta,
        short_dte: *short_dte,
        short_close_delta: *short_close_delta,
        short_close_dte: *short_close_dte,
        short_close_profit: *short_close_profit,
        slippage: *slippage,
        stop_loss: *stop_loss,
        profit_target: *profit_target,
    };
    println!("Strategy params: {}", strategy_params);
}
}

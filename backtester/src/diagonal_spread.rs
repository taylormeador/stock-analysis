use chrono::{NaiveDate, Duration};
use postgres::Client;
use crate::task_status_tracker::TaskStatusTracker;
use crate::option_contract::{get_option_contracts, OptionContract};
use itertools::iproduct;
use std::fmt;
use std::collections::BTreeSet;
use ordered_float::OrderedFloat;

enum TransactionType {
    BTO,
    STO,
    BTC,
    STC
}

#[derive(PartialEq)]
enum LegType {
    Long,
    Short,
}

struct DiagonalSpreadParamGrid {
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

impl DiagonalSpreadParamGrid {
    fn iter(&self) -> impl Iterator<Item = DiagonalSpreadParams> + '_ {
        // Lazily produce every combination of strategy parameters
        iproduct!(
            &self.long_delta,
            &self.long_dte,
            &self.long_close_dte,
            &self.short_delta,
            &self.short_dte,
            &self.short_close_delta,
            &self.short_close_dte,
            &self.short_close_profit,
            &self.slippage,
            &self.stop_loss,
            &self.profit_target,
        ).map(|(long_delta, long_dte, long_close_dte, short_delta, short_dte, short_close_delta, short_close_dte, short_close_profit, slippage, stop_loss, profit_target)| {
            DiagonalSpreadParams {
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
            }
        })
    }
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

impl DiagonalSpreadStrategy {
    fn run(&self, option_contracts: &[OptionContract]) {
        // Iterate over all dates with options data, from start_date
        let unique_dates: BTreeSet<NaiveDate> = option_contracts
            .iter()
            .filter(|c| c.quote_date >= self.start_date)
            .map(|c| c.quote_date)
            .collect();

        let mut initial_position: Option<DiagonalSpreadPosition> = None;
        for date in &unique_dates {
            let current_chain = option_contracts
            .iter()
            .filter(|c| c.quote_date == *date)
            .collect::<Vec<&OptionContract>>();
            
            // On the first day of the backtest, open the spread
            if initial_position.is_none() {
                initial_position = Some(DiagonalSpreadPosition::new(&current_chain, &self.strategy_params));
            }

            let position = initial_position.as_mut().unwrap();
        }
    }
}

struct DiagonalSpreadPosition<'a> {
    long_call: OptionContract,
    short_call: OptionContract,
    strategy_params: &'a DiagonalSpreadParams
}

impl<'a> DiagonalSpreadPosition<'a> {
    pub fn new(current_chain: &[&OptionContract], params: &'a DiagonalSpreadParams) -> Self {
        let long_call = Self::find_call(current_chain, params, LegType::Long);
        let short_call = Self::find_call(current_chain, params, LegType::Short);
        
        DiagonalSpreadPosition {
            long_call: long_call,
            short_call: short_call,
            strategy_params:  params,
        }
    }

    fn find_call(current_chain: &[&OptionContract], params: &DiagonalSpreadParams, long_short: LegType) -> OptionContract {
        let (target_dte, target_delta) = match long_short {
            LegType::Long => (params.long_dte, params.long_delta),
            LegType::Short => (params.short_dte, params.short_delta),
        };

        // Score the contract based on normalized distance from dte and delta
        // TODO rework contract selection to match intuition
        let best_contract = current_chain.iter().min_by_key(|c| {
            let dte_diff = ((c.expiration - current_chain[0].quote_date).num_days() - target_dte as i64).abs();
            let delta_diff = (c.delta - target_delta).abs();
            let score = dte_diff as f64 / target_dte as f64 + delta_diff / target_delta;
            OrderedFloat(score)
        }).expect(&format!("No contracts found on {}", current_chain[0].quote_date));

        return (*best_contract).clone()
    }
}

pub fn run_backtest(client: Client, tracker: TaskStatusTracker, ticker: &str, window_start_date: NaiveDate, window_end_date: NaiveDate) {
    let param_grid = DiagonalSpreadParamGrid {
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

    // Add long option max dte to window for options
    let max_dte = *param_grid.long_dte.iter().max().unwrap() as i64;
    let naive_datetime = window_end_date.and_hms_opt(0, 0, 0).unwrap();
    let duration_to_add = Duration::days(max_dte);
    let option_end_date = naive_datetime + duration_to_add;
    let option_contracts = get_option_contracts(client, &ticker, window_start_date, option_end_date.date());

    // Iterate through all strategy param combos and perform the backtest
    for strategy_params in param_grid.iter() {
        let strategy = DiagonalSpreadStrategy {
            ticker: ticker.to_string(),
            start_date: window_start_date,
            strategy_params: strategy_params
        };
        strategy.run(&option_contracts)

    }
}

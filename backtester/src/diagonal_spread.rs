use chrono::{NaiveDate, Duration, TimeDelta};
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

#[derive(Debug)]
enum CloseReason {
    LongCloseDTE,
    StopLoss,
    ProfitTarget
}

#[derive(PartialEq)]
enum LegType {
    Long,
    Short,
}

struct DiagonalSpreadParamGrid {
    long_delta: Vec<f64>,
    long_dte: Vec<i32>,
    long_close_dte: Vec<i64>,
    short_delta: Vec<f64>,
    short_dte: Vec<i32>,
    short_close_delta: Vec<f64>,
    short_close_dte: Vec<i64>,
    short_close_profit: Vec<f64>,
    slippage_pct: Vec<f64>,
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
            &self.slippage_pct,
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
                slippage_pct: *slippage,
                stop_loss_pct: *stop_loss,
                profit_target_pct: *profit_target,
            }
        })
    }
}

struct DiagonalSpreadParams {
    long_delta: f64,
    long_dte: i32,
    long_close_dte: i64,
    short_delta: f64,
    short_dte: i32,
    short_close_delta: f64,
    short_close_dte: i64,
    short_close_profit: f64,
    slippage_pct: f64,
    stop_loss_pct: f64,
    profit_target_pct: f64,
}

impl fmt::Display for DiagonalSpreadParams {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "long_delta={} long_dte={} long_close_dte={} short_delta={} short_dte={} short_close_delta={} short_close_dte={} short_close_profit={} slippage={} stop_loss={} profit_target={}",
        self.long_delta, self.long_dte, self.long_close_dte, self.short_delta, self.short_dte,
        self.short_close_delta, self.short_close_dte, self.short_close_profit, self.slippage_pct,
        self.stop_loss_pct, self.profit_target_pct)
    }
}

struct DiagonalSpreadStrategy {
    ticker: String,
    start_date: NaiveDate,
    params: DiagonalSpreadParams
}

impl DiagonalSpreadStrategy {
    fn run(&self, option_contracts: &[OptionContract]) -> Option<DiagonalSpreadPosition> {
        // Iterate over all dates with options data, from start_date
        // Each day, update the position and follow the rules laid out by the parameters
        let unique_dates: BTreeSet<NaiveDate> = option_contracts
            .iter()
            .filter(|c| c.quote_date >= self.start_date)
            .map(|c| c.quote_date)
            .collect();

        
        let mut initial_position: Option<DiagonalSpreadPosition> = None;
        for current_date in &unique_dates {
            let current_chain = option_contracts
            .iter()
            .filter(|c| c.quote_date == *current_date)
            .collect::<Vec<&OptionContract>>();

            // On the first day of the simulation, open the position.
            if initial_position.is_none() {
                initial_position = Some(DiagonalSpreadPosition::new(&current_chain, &self.params));
                log::debug!("Opening new position {:?}", initial_position);
            }

            // Update the position according to today's contracts
            let position = initial_position.as_mut().unwrap();
            position.update_position(&current_chain);

            // Handle the closing or rolling the position
            if position.current_value <= position.stop_loss_value {
                position.close(CloseReason::StopLoss);
                break
            }
            if position.current_value >= position.profit_target_value {
                position.close(CloseReason::ProfitTarget);
                break
            }
            if position.long_call.expiration - *current_date <= TimeDelta::days(self.params.long_close_dte) {
                position.close(CloseReason::LongCloseDTE);
                break
            }

            if position.short_value <= position.short_price * (1.0 - self.params.short_close_profit) {
                log::debug!("Rolling short call due to profit target");
                position.roll_short_call(&current_chain, self.params.short_dte, self.params.short_delta);

            } else if position.short_call.delta >= self.params.short_close_delta {
                log::debug!("Rolling short call due to delta");
                position.roll_short_call(&current_chain, self.params.short_dte, self.params.short_delta);

            } else if position.short_call.expiration - *current_date <= TimeDelta::days(self.params.short_close_dte) {
                log::debug!("Rolling short call due to DTE");
                position.roll_short_call(&current_chain, self.params.short_dte, self.params.short_delta);
            }
        }
        initial_position
    }
}


#[derive(Debug)]
struct DiagonalSpreadPosition {
    long_call: OptionContract,
    long_value: f64,
    long_price: f64,
    short_call: OptionContract,
    short_value: f64,
    short_price: f64,
    current_value: f64,
    initial_debit: f64,
    cost_basis: f64,
    stop_loss_value: f64,
    profit_target_value: f64,
    slippage_pct: f64,
}

impl DiagonalSpreadPosition {
    pub fn new(current_chain: &[&OptionContract], params: &DiagonalSpreadParams) -> Self {
        let long_call = Self::find_call(current_chain, params.long_dte, params.long_delta);
        let short_call = Self::find_call(current_chain, params.short_dte, params.short_delta);
        
        let (current_value, long_value, short_value) = Self::calc_values_from(&long_call, &short_call, &params.slippage_pct);
        
        // The price is what we pay to enter at, which is closer to ask for longs,
        // and closer to the bid for shorts
        let long_price = long_call.mid + (long_call.mid * params.slippage_pct);
        let short_price = short_call.mid - (short_call.mid * params.slippage_pct);

        // Stop loss and profit target are based on what we actually paid to enter the position
        let initial_debit = long_price - short_price;
        let total_debit = long_price - short_price;
        let stop_loss_value = initial_debit * (1.0 - params.stop_loss_pct);
        let profit_target_value = initial_debit * (1.0 + params.profit_target_pct);

        DiagonalSpreadPosition {
            long_call,
            long_value,
            long_price,
            short_call,
            short_value,
            short_price,
            current_value,
            initial_debit,
            cost_basis: total_debit,
            stop_loss_value,
            profit_target_value,
            slippage_pct: params.slippage_pct,
        }
    }

    fn find_call(current_chain: &[&OptionContract], target_dte: i32, target_delta: f64) -> OptionContract {
        // TODO rework contract selection to match intuition
        let best_contract = current_chain.iter().min_by_key(|c| {
            let dte_diff = ((c.expiration - current_chain[0].quote_date).num_days() - target_dte as i64).abs();
            let delta_diff = (c.delta - target_delta).abs();
            let score = dte_diff as f64 / target_dte as f64 + delta_diff / target_delta;
            OrderedFloat(score)
        }).expect(&format!("No contracts found on {}", current_chain[0].quote_date));

        return (*best_contract).clone()
    }

    fn roll_short_call(&mut self, current_chain: &[&OptionContract], target_dte: i32, target_delta: f64) {
        // We BTC so cost_basis goes up
        self.cost_basis = self.cost_basis + self.short_value;

        // STO a new one
        let new_call = Self::find_call(current_chain, target_dte, target_delta);
        self.short_call = new_call;

        // Update values/prices
        self.calc_values();
        self.short_price = self.short_call.mid - (self.short_call.mid * self.slippage_pct);
        self.cost_basis = self.cost_basis - self.short_price;

        log::debug!("rolled call to {:?}", self.short_call);
    }

    fn close(&mut self, close_reason: CloseReason) {
        log::debug!("Closing position due to {:?}", close_reason);
        // TODO Do we want to actually go through the motions of selling?
        self.cost_basis = self.cost_basis - self.current_value
        // TODO write to db
    }

    fn calc_values_from(long_call: &OptionContract, short_call: &OptionContract, slippage_pct: &f64) -> (f64, f64, f64) {
        // The value is what we have to sell at, which is closer to bid for longs, and closer to ask for shorts
        let long_value = long_call.mid - (long_call.spread * slippage_pct);
        let short_value = short_call.mid + (short_call.spread *slippage_pct);
        let current_value = long_value - short_value;

        (current_value, long_value, short_value)
    }

    fn calc_values(&mut self) {
        let (current_value, long_value, short_value) = Self::calc_values_from(&self.long_call, &self.short_call, &self.slippage_pct);
        self.current_value = current_value;        
        self.long_value = long_value;
        self.short_value = short_value;
    }

    fn update_position(&mut self, current_chain: &[&OptionContract]) {
        // Update position to reflect today's prices
        let new_long_call = current_chain.iter().filter(|c| {
            c.expiration == self.long_call.expiration && c.strike == self.long_call.strike
        }).collect::<Vec<&&OptionContract>>();
        if new_long_call.len() != 1 {
            panic!("Found more than one contract for given long strike/expiration");
        }
        self.long_call = (*new_long_call[0]).clone();

        let new_short_call = current_chain.iter().filter(|c| {
            c.expiration == self.short_call.expiration && c.strike == self.short_call.strike
        }).collect::<Vec<&&OptionContract>>();
        if new_short_call.len() != 1 {
            panic!("Found more than one contract for given short contract/expiration")
        }
        self.short_call = (*new_short_call[0]).clone();

        self.calc_values();
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
        slippage_pct: vec![0.5, 0.75],
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
        log::debug!("Running backtest with params: {}", strategy_params);
        let strategy = DiagonalSpreadStrategy {
            ticker: ticker.to_string(),
            start_date: window_start_date,
            params: strategy_params
        };
        let end_position = strategy.run(&option_contracts);
        log::debug!("Simulation ended. Final position: {:?}", end_position);
        log::debug!("******************************************");
        

    }
}

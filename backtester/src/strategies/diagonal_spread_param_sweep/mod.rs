use crate::option_contract::{get_option_contracts, OptionContract};
use crate::task_status_tracker::TaskStatusTracker;
use crate::DbPool;
use chrono::{Duration, NaiveDate, TimeDelta};
use ordered_float::OrderedFloat;
use rayon::prelude::*;
use std::collections::BTreeSet;
use std::sync::mpsc;
use std::thread;

pub mod params;
use params::{DiagonalSpreadParams, DiagonalSpreadRunnerGrid};

// TODO I don't think backtestTransaction belongs in position, and RunLedger might need a new home
pub mod position;
use position::DiagonalSpreadPosition;

pub mod results;
use results::DiagonalSpreadRunResult;

pub mod ledger;
use ledger::{BacktestTransaction, CloseReason, RunLedger, TransactionType};

#[derive(Debug)]
struct DiagonalSpreadRunner {
    start_date: NaiveDate,
    params: DiagonalSpreadParams,
}

impl DiagonalSpreadRunner {
    fn run(
        &mut self,
        option_contracts: &[OptionContract],
    ) -> Result<DiagonalSpreadRunResult, String> {
        // Iterate over all dates with options data, from start_date
        // Each day, update the position and follow the rules laid out by the parameters
        let unique_dates: BTreeSet<NaiveDate> = option_contracts
            .iter()
            .filter(|c| c.quote_date >= self.start_date)
            .map(|c| c.quote_date)
            .collect();

        let mut initial_position: Option<DiagonalSpreadPosition> = None;
        let mut ledger = RunLedger::new();
        let mut stop_loss_value: Option<f64> = None;
        let mut profit_target_value: Option<f64> = None;
        for current_date in &unique_dates {
            let current_chain = option_contracts
                .iter()
                .filter(|c| c.quote_date == *current_date)
                .collect::<Vec<&OptionContract>>();

            // On the first day of the simulation, open the position.
            if initial_position.is_none() {
                initial_position = Some(self.open_position(&mut ledger, &current_chain));
                stop_loss_value = Some(ledger.initial_debit() * (1.0 - self.params.stop_loss_pct));
                profit_target_value =
                    Some(ledger.initial_debit() * (1.0 + self.params.profit_target_pct));
            }

            // Update the position according to today's contracts
            let position = initial_position.as_mut().unwrap();
            position.update_position(&current_chain);

            // Handle closing the position
            let (long_value, short_value) = position.current_values(&self.params.slippage_pct);
            let current_value = long_value - short_value;
            if current_value <= stop_loss_value.unwrap() {
                log::debug!("Closing position due to stop loss");
                self.close_position(position, &mut ledger, CloseReason::StopLoss);
                break;
            }
            if current_value >= profit_target_value.unwrap() {
                log::debug!("Closing position due to profit target");
                self.close_position(position, &mut ledger, CloseReason::ProfitTarget);
                break;
            }
            if position.long_call.expiration - *current_date
                <= TimeDelta::days(self.params.long_close_dte)
            {
                log::debug!("Closing position due to long DTE");
                self.close_position(position, &mut ledger, CloseReason::LongCloseDTE);
                break;
            }

            // Manage short call
            if short_value <= ledger.short_price * (1.0 - self.params.short_close_profit) {
                log::debug!("Rolling short call due to profit target");
                self.roll_short_call(position, &mut ledger, &current_chain);
            } else if position.short_call.delta >= self.params.short_close_delta {
                log::debug!("Rolling short call due to delta");
                self.roll_short_call(position, &mut ledger, &current_chain);
            } else if position.short_call.expiration - *current_date
                <= TimeDelta::days(self.params.short_close_dte)
            {
                log::debug!("Rolling short call due to DTE");
                self.roll_short_call(position, &mut ledger, &current_chain);
            }
        }

        let position = initial_position.ok_or("No position was opened")?;
        Ok(DiagonalSpreadRunResult::new(position, ledger))
    }

    fn open_position(
        &mut self,
        run_ledger: &mut RunLedger,
        current_chain: &[&OptionContract],
    ) -> DiagonalSpreadPosition {
        // This function handles the details of calling helpers and returns the inferred stop loss and profit target values.
        let long_call =
            self.find_call(&current_chain, self.params.long_dte, self.params.long_delta);
        let short_call = self.find_call(
            &current_chain,
            self.params.short_dte,
            self.params.short_delta,
        );
        let position = DiagonalSpreadPosition::new(long_call, short_call);
        log::debug!("Opened new position {:?}", position);

        let bto_tx = BacktestTransaction {
            transaction_type: TransactionType::BTO,
            contract: position.long_call.clone(),
            quantity: 1,
        };
        let long_price = run_ledger.handle_tx(bto_tx, &self.params.slippage_pct);

        let sto_tx = BacktestTransaction {
            transaction_type: TransactionType::STO,
            contract: position.short_call.clone(),
            quantity: 1,
        };
        let short_price = run_ledger.handle_tx(sto_tx, &self.params.slippage_pct);

        // Stop loss and profit target are based on what we actually paid to enter the position
        let initial_debit = long_price - short_price;
        run_ledger.set_initial_debit(initial_debit);

        position
    }

    fn find_call(
        &self,
        current_chain: &[&OptionContract],
        target_dte: i32,
        target_delta: f64,
    ) -> OptionContract {
        // TODO rework contract selection to match intuition
        let best_contract = current_chain
            .iter()
            .min_by_key(|c| {
                let dte_diff = ((c.expiration - current_chain[0].quote_date).num_days()
                    - target_dte as i64)
                    .abs();
                let delta_diff = (c.delta - target_delta).abs();
                let score = dte_diff as f64 / target_dte as f64 + delta_diff / target_delta;
                OrderedFloat(score)
            })
            .expect(&format!(
                "No contracts found on {}",
                current_chain[0].quote_date
            ));

        return (*best_contract).clone();
    }

    fn roll_short_call(
        &mut self,
        position: &mut DiagonalSpreadPosition,
        run_ledger: &mut RunLedger,
        current_chain: &[&OptionContract],
    ) {
        // To roll a short call, we BTC the existing one and then STO a new one at the target DTE/delta
        let btc_tx = BacktestTransaction {
            transaction_type: TransactionType::BTC,
            contract: position.short_call.clone(),
            quantity: 1,
        };
        run_ledger.handle_tx(btc_tx, &self.params.slippage_pct);

        // TODO I could let find_call get dte and delta from self
        let new_call = self.find_call(
            current_chain,
            self.params.short_dte,
            self.params.short_delta,
        );
        let sto_tx = BacktestTransaction {
            transaction_type: TransactionType::STO,
            contract: new_call.clone(),
            quantity: 1,
        };
        run_ledger.handle_tx(sto_tx, &self.params.slippage_pct);
        log::debug!("rolled call to {:?}", new_call);

        position.short_call = new_call;
    }

    fn close_position(
        &self,
        position: &mut DiagonalSpreadPosition,
        ledger: &mut RunLedger,
        close_reason: CloseReason,
    ) {
        // Close the contracts, assuming they have been updated to the current_chain
        let btc_tx = BacktestTransaction {
            transaction_type: TransactionType::BTC,
            contract: position.short_call.clone(),
            quantity: 1,
        };
        ledger.handle_tx(btc_tx, &self.params.slippage_pct);

        let stc_tx = BacktestTransaction {
            transaction_type: TransactionType::STC,
            contract: position.long_call.clone(),
            quantity: 1,
        };
        ledger.handle_tx(stc_tx, &self.params.slippage_pct);

        ledger.close_reason = Some(close_reason);
        ledger.end_date = Some(position.long_call.quote_date);
    }
}

pub fn run_backtest(
    pool: &DbPool,
    tracker: &TaskStatusTracker,
    ticker: String,
    window_start_date: NaiveDate,
    window_end_date: NaiveDate,
) {
    let long_dte_params = vec![180, 270, 365];
    let max_dte = *long_dte_params.iter().max().unwrap() as i64;
    let option_end_date = window_end_date + Duration::days(max_dte + 30);
    let option_contracts = get_option_contracts(pool, &ticker, window_start_date, option_end_date);

    let valid_start_dates: Vec<NaiveDate> = option_contracts
        .iter()
        .filter(|c| c.quote_date >= window_start_date && c.quote_date <= window_end_date)
        .map(|c| c.quote_date)
        .collect::<BTreeSet<NaiveDate>>()
        .into_iter()
        .collect();

    let runner_grid = DiagonalSpreadRunnerGrid {
        start_date: valid_start_dates,
        long_delta: vec![0.9, 0.8, 0.7, 0.6],
        long_dte: long_dte_params,
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

    let runners: Vec<DiagonalSpreadRunner> = runner_grid.iter().collect();
    let total_runs = runners.len();
    let completed = std::sync::atomic::AtomicUsize::new(0);

    let (tx, rx) = mpsc::channel::<(DiagonalSpreadRunner, DiagonalSpreadRunResult)>();

    let pool_clone = pool.clone();
    let ticker_owned = ticker.clone();
    let writer = thread::spawn(move || {
        let sql = "
            INSERT INTO backtest_runs (
                strategy_type, ticker, start_date, end_date, parameters,
                pnl, fees, commissions, sharpe_ratio, sortino_ratio, max_drawdown, close_reason
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12);
        ";

        let mut client = pool_clone.get().unwrap();
        let mut batch: Vec<(DiagonalSpreadRunner, DiagonalSpreadRunResult)> = Vec::new();
        let batch_size = 1000;

        for (runner, result) in rx {
            batch.push((runner, result));
            if batch.len() >= batch_size {
                let mut db_tx = client.transaction().unwrap();
                for (r, res) in &batch {
                    let params_json = serde_json::to_value(&r.params).unwrap();
                    db_tx
                        .execute(
                            sql,
                            &[
                                &"diagonal_spread_param_sweep",
                                &ticker_owned,
                                &r.start_date,
                                &res.ledger.end_date,
                                &params_json,
                                &res.ledger.cost_basis,
                                &res.ledger.fees,
                                &res.ledger.commissions,
                                &res.sharpe_ratio,
                                &res.sortino_ratio,
                                &res.max_drawdown,
                                &res.ledger.close_reason.as_ref().map(|r| r.to_string()),
                            ],
                        )
                        .unwrap();
                }
                db_tx.commit().unwrap();
                log::info!("Committed batch of {} results", batch.len());
                batch.clear();
            }
        }

        if !batch.is_empty() {
            let mut db_tx = client.transaction().unwrap();
            for (r, res) in &batch {
                let params_json = serde_json::to_value(&r.params).unwrap();
                db_tx
                    .execute(
                        sql,
                        &[
                            &"diagonal_spread_param_sweep",
                            &ticker_owned,
                            &r.start_date,
                            &res.ledger.end_date,
                            &params_json,
                            &res.ledger.cost_basis,
                            &res.ledger.fees,
                            &res.ledger.commissions,
                            &res.sharpe_ratio,
                            &res.sortino_ratio,
                            &res.max_drawdown,
                            &res.ledger.close_reason.as_ref().map(|r| r.to_string()),
                        ],
                    )
                    .unwrap();
            }
            db_tx.commit().unwrap();
            log::info!("Committed final batch of {} results", batch.len());
        }
    });

    runners.into_par_iter().for_each_with(tx, |tx, mut runner| {
        match runner.run(&option_contracts) {
            Ok(result) => {
                let n = completed.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1;
                tracker.update_progress(n as f64 / total_runs as f64);
                tracker.update_status_message(&format!(
                    "Running diagonal spread parameter sweep #{}/{} on {}",
                    n, total_runs, ticker
                ));
                tx.send((runner, result)).unwrap();
            }
            Err(e) => {
                log::error!("Run failed with params {:?}: {}", runner.params, e);
            }
        }
    });

    writer.join().unwrap();
}

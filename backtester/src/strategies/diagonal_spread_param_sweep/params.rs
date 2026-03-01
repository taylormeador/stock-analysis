use crate::strategies::diagonal_spread_param_sweep::DiagonalSpreadRunner;
use chrono::NaiveDate;
use itertools::iproduct;
use serde::Serialize;
use std::fmt;

pub struct DiagonalSpreadRunnerGrid {
    pub start_date: Vec<NaiveDate>,
    pub long_delta: Vec<f64>,
    pub long_dte: Vec<i32>,
    pub long_close_dte: Vec<i64>,
    pub short_delta: Vec<f64>,
    pub short_dte: Vec<i32>,
    pub short_close_delta: Vec<f64>,
    pub short_close_dte: Vec<i64>,
    pub short_close_profit: Vec<f64>,
    pub slippage_pct: Vec<f64>,
    pub stop_loss: Vec<f64>,
    pub profit_target: Vec<f64>,
}

impl DiagonalSpreadRunnerGrid {
    pub fn iter(&self) -> impl Iterator<Item = DiagonalSpreadRunner> + '_ {
        // Lazily produce every combination of start_date + strategy parameters
        iproduct!(
            &self.start_date,
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
        )
        .map(
            |(
                start_date,
                long_delta,
                long_dte,
                long_close_dte,
                short_delta,
                short_dte,
                short_close_delta,
                short_close_dte,
                short_close_profit,
                slippage,
                stop_loss,
                profit_target,
            )| {
                let params = DiagonalSpreadParams {
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
                };

                DiagonalSpreadRunner {
                    start_date: *start_date,
                    params: params,
                }
            },
        )
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct DiagonalSpreadParams {
    pub long_delta: f64,
    pub long_dte: i32,
    pub long_close_dte: i64,
    pub short_delta: f64,
    pub short_dte: i32,
    pub short_close_delta: f64,
    pub short_close_dte: i64,
    pub short_close_profit: f64,
    pub slippage_pct: f64,
    pub stop_loss_pct: f64,
    pub profit_target_pct: f64,
}

impl fmt::Display for DiagonalSpreadParams {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "long_delta={} long_dte={} long_close_dte={} short_delta={} short_dte={} short_close_delta={} short_close_dte={} short_close_profit={} slippage={} stop_loss={} profit_target={}",
        self.long_delta, self.long_dte, self.long_close_dte, self.short_delta, self.short_dte,
        self.short_close_delta, self.short_close_dte, self.short_close_profit, self.slippage_pct,
        self.stop_loss_pct, self.profit_target_pct)
    }
}

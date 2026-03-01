use crate::option_contract::OptionContract;
use crate::strategies::diagonal_spread_param_sweep::position;
use chrono::NaiveDate;
use std::fmt;

#[derive(Debug)]
pub enum CloseReason {
    LongCloseDTE,
    StopLoss,
    ProfitTarget,
}

impl fmt::Display for CloseReason {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            CloseReason::LongCloseDTE => write!(f, "{}", "long_close_dte"),
            CloseReason::StopLoss => write!(f, "{}", "stop_loss"),
            CloseReason::ProfitTarget => write!(f, "{}", "profit_target"),
        }
    }
}

#[derive(PartialEq, Clone)]
pub enum LegType {
    Long,
    Short,
}

#[derive(Clone, PartialEq)]
pub enum TransactionType {
    BTO,
    STO,
    BTC,
    STC,
}

#[derive(Clone)]
pub struct BacktestTransaction {
    pub transaction_type: TransactionType,
    pub contract: OptionContract,
    pub quantity: i32,
}

pub struct RunLedger {
    pub daily_values: Vec<f64>, // The value (mark) of the position each day
    pub transactions: Vec<BacktestTransaction>,
    pub short_price: f64, // The fill_price of the STO tx for the currently held short call
    pub initial_debit: Option<f64>, // Debit of initial position opening (not including commissions/fees)
    pub cost_basis: f64,            // Cumulative debits/credits (not including commissions/fees)
    pub fees: f64,
    pub commissions: f64,
    pub close_reason: Option<CloseReason>,
    pub end_date: Option<NaiveDate>,
}

impl RunLedger {
    pub fn new() -> Self {
        Self {
            daily_values: Vec::new(),
            transactions: Vec::new(),
            short_price: 0.0,
            initial_debit: None,
            cost_basis: 0.0,
            fees: 0.0,
            commissions: 0.0,
            close_reason: None,
            end_date: None,
        }
    }

    pub fn handle_tx(&mut self, tx: BacktestTransaction, slippage_pct: &f64) -> f64 {
        // The fill price is what we pay to enter/exit at.
        // This is closer to ask for buys, and closer to the bid for sells
        let fill_price = match tx.transaction_type {
            TransactionType::BTO | TransactionType::BTC => {
                tx.contract.mid + (tx.contract.mid * slippage_pct)
            }
            TransactionType::STO | TransactionType::STC => {
                tx.contract.mid - (tx.contract.mid * slippage_pct)
            }
        };
        let signed_fill = match tx.transaction_type {
            TransactionType::BTO | TransactionType::BTC => -fill_price,
            TransactionType::STO | TransactionType::STC => fill_price,
        };

        // TODO does this oversimplify the roll handling for options that hit profit target?
        if tx.transaction_type == TransactionType::STO {
            self.short_price = fill_price;
        }

        self.cost_basis += signed_fill;
        self.fees += 0.0004 * tx.quantity as f64;
        self.commissions += 0.01 * tx.quantity as f64;

        self.transactions.push(tx);
        fill_price
    }

    pub fn set_initial_debit(&mut self, value: f64) {
        if self.initial_debit.is_some() {
            panic!("initial_debit already set");
        }
        self.initial_debit = Some(value);
    }

    pub fn initial_debit(&self) -> f64 {
        self.initial_debit.expect("initial_debit not yet set")
    }
}

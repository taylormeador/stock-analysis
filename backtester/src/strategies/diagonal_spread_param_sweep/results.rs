use crate::strategies::diagonal_spread_param_sweep::RunLedger;

pub struct DiagonalSpreadRunResult {
    pub ledger: RunLedger,
    pub sharpe_ratio: f64,
    pub sortino_ratio: f64,
    pub max_drawdown: f64,
}

impl DiagonalSpreadRunResult {
    pub fn new(ledger: RunLedger) -> Self {
        let risk_free_rate = 3.0; // TODO use 3 month T-Bill

        let daily_returns: Vec<f64> = ledger
            .daily_values
            .windows(2)
            .map(|pair| (pair[1] - pair[0]) / pair[0])
            .collect();

        let excess_returns: Vec<f64> = daily_returns
            .iter()
            .map(|r| r - (risk_free_rate / 252.0))
            .collect();

        // Sharpe ratio
        let mean = excess_returns.iter().sum::<f64>() / excess_returns.len() as f64;
        let variance = excess_returns
            .iter()
            .map(|r| (r - mean).powi(2))
            .sum::<f64>()
            / excess_returns.len() as f64;
        let std_dev = variance.sqrt();
        let sharpe_ratio = (mean / std_dev) * (252.0_f64).sqrt();

        // Sortino ratio
        let downside_returns: Vec<f64> = excess_returns
            .iter()
            .filter(|&&r| r < 0.0)
            .copied()
            .collect();
        let downside_mean = downside_returns.iter().sum::<f64>() / downside_returns.len() as f64;
        let downside_variance = downside_returns
            .iter()
            .map(|r| (r - downside_mean).powi(2))
            .sum::<f64>()
            / downside_returns.len() as f64;
        let sortino_ratio = (mean / downside_variance.sqrt()) * (252.0_f64).sqrt();

        // Max drawdown
        let max_drawdown = {
            let mut peak = f64::NEG_INFINITY;
            ledger
                .daily_values
                .iter()
                .map(|&v| {
                    peak = peak.max(v);
                    (v - peak) / peak
                })
                .fold(0.0_f64, f64::min)
        };

        Self {
            ledger,
            sharpe_ratio,
            sortino_ratio,
            max_drawdown,
        }
    }
}

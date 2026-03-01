use crate::option_contract::OptionContract;

#[derive(Debug, Clone)]
pub struct DiagonalSpreadPosition {
    pub long_call: OptionContract,
    pub short_call: OptionContract,
}

impl DiagonalSpreadPosition {
    pub fn new(long_call: OptionContract, short_call: OptionContract) -> Self {
        DiagonalSpreadPosition {
            long_call: long_call.clone(),
            short_call: short_call.clone(),
        }
    }

    pub fn update_position(&mut self, current_chain: &[&OptionContract]) {
        // Update position to use contracts from today's option chain
        let new_long_call = current_chain
            .iter()
            .filter(|c| {
                c.expiration == self.long_call.expiration && c.strike == self.long_call.strike
            })
            .collect::<Vec<&&OptionContract>>();
        if new_long_call.len() != 1 {
            panic!("Found more than one contract for given long strike/expiration");
        }
        self.long_call = (*new_long_call[0]).clone();

        let new_short_call = current_chain
            .iter()
            .filter(|c| {
                c.expiration == self.short_call.expiration && c.strike == self.short_call.strike
            })
            .collect::<Vec<&&OptionContract>>();
        if new_short_call.len() != 1 {
            panic!("Found more than one contract for given short contract/expiration")
        }
        self.short_call = (*new_short_call[0]).clone();
    }

    pub fn current_values(&self, slippage_pct: &f64) -> (f64, f64) {
        // This function assumes that update_position() has been called for the current date.
        // The current value is what we would receive if we were to enter/exit right now.
        // This is closer to the bid for long options, and closer to the ask for short options.
        let long_value = self.long_call.mid - (self.long_call.mid * slippage_pct);
        let short_value = self.short_call.mid + (self.short_call.mid * slippage_pct);
        (long_value, short_value)
    }
}

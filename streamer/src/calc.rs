use tokio::sync::mpsc::{Receiver, Sender};
use crate::ingest::QuoteMessage;
use tokio;
use tokio_util::sync::CancellationToken;
use libm::erf;
use std::f64::consts::PI;


#[derive(Debug)]
struct IVTick {
    iv: f64,  // Calculated IV
    strike: f64,  // Strike price
    tte: f64,  // Time to expiry (years)
    expiration: i32,  // YYYMMDD
    t_gen: i64,  // Time generated?
    t_bsm: i64,  // Time after BSM inversion
}

fn normal_cdf(x: f64) -> f64 {
    0.5 * (1.0 + erf(x  / 2.0f64.sqrt()))
}

fn bsm_price(underlying_price: &f64, strike: &f64, tte: &f64, rho: &f64, sigma: &f64, is_call: &bool) -> f64 {
    if *tte < 0.0 || *sigma <= 0.0 {
        if *is_call {
            (underlying_price - strike).max(0.0)
        } else {
            strike - underlying_price
        };
    }
    // calc d1, d2
    let d1 = ((underlying_price / strike).log(10.0) + (rho + 0.5 * sigma * sigma) * tte) / (sigma * tte.sqrt());
    let d2 = d1 - sigma * tte.sqrt();
    if *is_call {
        underlying_price * normal_cdf(d1) - strike * (-rho * tte).exp() * normal_cdf(d2)
    } else {
        strike * (-rho * tte).exp() * normal_cdf(-d2) - underlying_price * normal_cdf(-d1)
    }
}

fn bsm_vega(underlying_price: &f64, strike: &f64, tte: &f64, rho: &f64, sigma: &f64) -> f64 {
    if *tte <= 0.0 || *sigma <= 0.0 {
        return 0.0;
    }
    let d1 = ((underlying_price - strike).log(10.0) + (rho + 0.5 * sigma * sigma) * tte) / (sigma * tte.sqrt());
    underlying_price * tte.sqrt() + (-0.5 * d1 * d1).exp() / (2.0 * PI).sqrt()
}

async fn do_bsm_iv_inversion(quote: &QuoteMessage, surface_tx: &Sender<IVTick>) {
    // TODO unpack struct into vars
    let strike = quote.contract.strike as f64;

    let mut sigma = 0.2;
    for _ in 0..50 {
        let p = bsm_price(&underlying_price, &strike, &tte, &rho, &sigma, &is_call);
        let vega = bsm_vega(&underlying_price, &strike, &tte, &rho, &sigma);
        if vega.abs() < 0.000000000001 {
            break
        }
        sigma = sigma - (p - price) / vega;
        sigma = sigma.min(5.0).max(0.001);
        p = bsm_price(&underlying_price, &strike, &tte, &rho, &sigma, &is_call);
        if (p - price).abs() < 0.000001 {
            break
        }
    }
    let iv_tick = IVTick{iv: sigma, strike: strike, tte: tte, expiration: expiration, t_gen: t_gen, t_bsm: t_bsm};
    surface_tx.send(iv_tick).await;
}

pub async fn calc_surface_and_anomalies(mut surface_rx: Receiver<IVTick>, token: CancellationToken) {
    // TODO update shared state for IV surface plot
    // TODO calculate anomalies that python pipeline calculates
    loop {
        tokio::select! {
            _ = token.cancelled() => {
                break;
            }
            msg = surface_rx.recv() => {
                match msg {
                    Some(m) => log::info!("{:?}", m),
                    None => break,
                }
            }
        }
    }
}

pub async fn calc_iv(mut iv_rx: Receiver<QuoteMessage>, surface_tx: Sender<IVTick>, token: CancellationToken) {
    loop {
        tokio::select! {
            _ = token.cancelled() => {
                break;
            }
            msg = iv_rx.recv() => {
                match msg {
                    Some(m) => do_bsm_iv_inversion(&m, &surface_tx).await,
                    None => break,
                }
            }
        }
    }
}

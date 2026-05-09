use std::env;
use dotenvy::dotenv;
use tokio_util::sync::CancellationToken;
use tokio::sync::mpsc::{Sender, Receiver, channel};

mod ingest;
mod calc;

#[tokio::main]
async fn main() {
    dotenv().ok();
    env_logger::init();

    let theta_data_ws = env::var("THETA_DATA_WS").unwrap();
    let ws_url = format!("{0}/v1/events", theta_data_ws);

    let theta_data_http = env::var("THETA_DATA_HTTP").unwrap();
    let contracts = ingest::fetch_contracts(&theta_data_http).await.expect("Failed to get contracts");
    
    let token = CancellationToken::new();
    let token_2 = token.clone();
    let token_3 = token.clone();

    // init channels
    let (iv_tx, iv_rx): (Sender<ingest::QuoteMessage>, Receiver<ingest::QuoteMessage>) = channel(32);
    // let (surface_tx, _) = channel(32);
    
    let t1 = tokio::spawn(ingest::ingest(ws_url, contracts, iv_tx, token_2));
    let t2 = tokio::spawn(calc::calc_iv(iv_rx, token_3));


    // Listen for interrupt
    loop {
        tokio::select! {
            _ = tokio::signal::ctrl_c() => {
                token.cancel();
                break;
            }
        }
    }

    // Wait for threads to shutdown cleanly
    let _ = t1.await;
    let _ = t2.await;
    
}

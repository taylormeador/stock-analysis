use std::env;
use dotenvy::dotenv;
use tokio_util::sync::CancellationToken;

mod pipeline;

#[tokio::main]
async fn main() {
    dotenv().ok();
    env_logger::init();

    let theta_data_ws = env::var("THETA_DATA_WS").unwrap();
    let ws_url = format!("{0}/v1/events", theta_data_ws);

    let theta_data_http = env::var("THETA_DATA_HTTP").unwrap();
    let contracts = pipeline::fetch_contracts(&theta_data_http).await.expect("Failed to get contracts");
    
    let token = CancellationToken::new();
    let token_2 = token.clone();
    
    let t1 = tokio::spawn(pipeline::ingest(ws_url, contracts, token_2));
    // tokio::spawn(pipeline::calc_iv(iv_channel));


    // Listen for interrupt
    loop {
        tokio::select! {
            _ = tokio::signal::ctrl_c() => {
                token.cancel();
                break;
            }
        }
    }

    let _ = t1.await;
    
}

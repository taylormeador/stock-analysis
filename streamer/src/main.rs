use std::env;
use dotenvy::dotenv;

use futures_util::{StreamExt, SinkExt};
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};

mod pipeline;

#[tokio::main]
async fn main() {
    dotenv().ok();
    env_logger::init();

    let theta_data_ws = env::var("THETA_DATA_WS").unwrap();
    let ws_url = format!("{0}/v1/events", theta_data_ws);

    let (ws_stream, _) = connect_async(&ws_url).await.expect("Failed to connect to theta data terminal");
    log::info!("WebSocket handshake has been successfully completed");

    let theta_data_http = env::var("THETA_DATA_HTTP").unwrap();
    
    let contracts = pipeline::fetch_contracts(&theta_data_http).await;
    log::info!("here");

    // let (mut write, mut read) = ws_stream.split();
    
    // TODO incrememnt id for separate streams
    // let payload = "{
    //     \"msg_type\": \"STREAM\",
    //     \"sec_type\": \"OPTION\",
    //     \"req_type\": \"TRADE\",
    //     \"add\": true,
    //     \"id\": 6,
    //     \"contract\": {
    //         \"root\": \"SPX\",
    //         \"expiration\": 20260515,
    //         \"strike\": 7250000,
    //         \"right\": \"C\"
    //     }
    // }";
    // write.send(Message::Text(payload.into())).await.expect("Failed to send payload");

    // // race between interrupt and message received
    // loop {
    //     tokio::select! {
    //         _ = tokio::signal::ctrl_c() => {
    //             // TODO cleanup and exit
    //             log::info!("ctrl-c");
    //             let stop_payload = "{
    //                     \"msg_type\": \"STOP\"
    //                 }";
    //             write.send(Message::Text(stop_payload.into())).await.expect("Failed to send payload");
    //             log::info!("stopped all streams");
    //             break;
    //         }
    //         msg = read.next() => {
    //             log::info!("{:?}", msg);
    //         }
    //     }
    // }
    
}

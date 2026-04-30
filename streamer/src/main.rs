use std::env;
use dotenvy::dotenv;

use futures_util::{StreamExt, SinkExt};
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};

#[tokio::main]
async fn main() {
    dotenv().ok();

    let theta_data_terminal = env::var("THETA_DATA_TERMINAL").unwrap();
    let url = format!("{0}/v1/events", theta_data_terminal);

    let (ws_stream, _) = connect_async(&url).await.expect("Failed to connect to theta data terminal");
    println!("WebSocket handshake has been successfully completed");

    let (mut write, mut read) = ws_stream.split();
    
    // TODO incrememnt id for separate streams
    let payload = "{
        \"msg_type\": \"STREAM\",
        \"sec_type\": \"OPTION\",
        \"req_type\": \"TRADE\",
        \"add\": false,
        \"id\": 1,
        \"contract\": {
            \"root\": \"SPXW\",
            \"expiration\": 20270315,
            \"strike\": 6800000,
            \"right\": \"C\"
        }
    }";
    write.send(Message::Text(payload.into())).await.expect("Failed to send payload");

    while let Some(msg) = read.next().await {
        println!("{:?}", msg);
    }
}

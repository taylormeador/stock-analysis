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
        \"add\": true,
        \"id\": 6,
        \"contract\": {
            \"root\": \"SPX\",
            \"expiration\": 20260515,
            \"strike\": 7250000,
            \"right\": \"C\"
        }
    }";
    write.send(Message::Text(payload.into())).await.expect("Failed to send payload");

    // race between interrupt and message received
    loop {
        tokio::select! {
            _ = tokio::signal::ctrl_c() => {
                // TODO cleanup and exit
                println!("ctrl-c");
                let stop_payload = "{
                        \"msg_type\": \"STOP\"
                    }";
                write.send(Message::Text(stop_payload.into())).await.expect("Failed to send payload");
                println!("stopped all streams");
                break;
            }
            msg = read.next() => {
                println!("{:?}", msg);
            }
        }
    }
    
}

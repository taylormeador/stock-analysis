use csv_async::AsyncReaderBuilder;
use futures_util::{StreamExt, SinkExt};
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message};
use tokio_util::sync::CancellationToken;
use tokio_util::io::StreamReader;
use futures::TryStreamExt;
use std::io;

// This is an option contract as given by the HTTP response
#[derive(serde::Deserialize, Debug)]
pub struct ContractResponse {
    symbol: String,
    expiration: String,
    strike: f64,
    right: String,
}

// This is an option contract as needed to write to the WebSocket 
pub struct ContractSubscribe {
    root: String,
    expiration: String,
    strike: f64,
    right: String,
}

impl From<ContractResponse> for ContractSubscribe {
    fn from(r: ContractResponse) -> Self {
        let expiration = r.expiration.replace("-", "");
        let strike = r.strike * 1000.0;
        let right = match r.right.to_uppercase() == "CALL" {
            true => "C",
            false => "P"
        };

        ContractSubscribe { root: r.symbol, expiration: expiration, strike: strike, right: right.to_string() }
    }
}

pub async fn fetch_contracts(http_base: &str) -> Result<Vec<ContractSubscribe>, Box<dyn std::error::Error>> {
    // Fetch all active SPX/SPXW option contracts from the list contracts endpoint.
    // 
    // Response is streamed CSV: "SPX","2026-03-20",6475.000,"CALL"
    // Converted to subscription format: {root, expiration (YYYYMMDD int), strike (1/10th cent int), right (C/P)}
    
    // TODO add SPXW contracts up to 10k contracts total

    let mut url = format!("{http_base}/v3/option/list/contracts/quote?symbol=SPX&date=20250428");
    let mut contracts: Vec<ContractSubscribe> = Vec::new();
    loop {
        {
            log::info!("Sending GET {}", url);
            let response = reqwest::get(url).await?;
            let headers = response.headers().clone();
            let err_closure = {
                |e| io::Error::new(io::ErrorKind::Other, e)
            };
            let stream = response.bytes_stream().map_err(err_closure);
            let stream_reader = StreamReader::new(stream);
            let mut async_reader = AsyncReaderBuilder::new().create_deserializer(stream_reader);
            let mut lines = async_reader.deserialize::<ContractResponse>();
            
            while let Some(line) = lines.next().await {
                    let contract_response = line?;
                    contracts.push(ContractSubscribe::from(contract_response));
                }
            
            if let Some(next_page) = headers.get("Next-Page") {
                match next_page.to_str() {
                    Ok(s) if s != "null" => url = s.to_string(),
                    _ => break
                }
            } else {
                break
            }
        }
    }
    
    Ok(contracts)
}

#[derive(Debug)]
enum MessageType {
    Status(StatusMessage),
    State(StateMessage),
    ReqResponse(ReqResponseMessage),
    Quote(QuoteMessage),
    Trade(TradeMessage),
}

#[derive(serde::Deserialize, Debug)]
struct Header {
    r#type: String,
    status: String,
    response: Option<String>,
    req_id: Option<i64>,
    state: Option<String>,
}

#[derive(serde::Deserialize, Debug)]
struct Contract {
    security_type: String,
    root: String,
    expiration: i64,
    strike: i64,
    right: String,
}

#[derive(serde::Deserialize, Debug)]
struct Quote {
    ms_of_day: i64,
    bid_size: i64,
    bid_exchange: i64,
    bid: f64,
    bid_condition: i64,
    ask_size: i64,
    ask_exchange: i64,
    ask: f64,
    ask_condition: i64,
    date: i64,
}

#[derive(serde::Deserialize, Debug)]
struct Trade {
    // TODO
}

#[derive(serde::Deserialize, Debug)]
struct StatusMessage {
    header: Header,
}

#[derive(serde::Deserialize, Debug)]
struct StateMessage {
    header: Header,
}

#[derive(serde::Deserialize, Debug)]
struct ReqResponseMessage {
    header: Header,
}

#[derive(serde::Deserialize, Debug)]
struct QuoteMessage {
    header: Header,
    contract: Contract,
    quote: Quote,
}

#[derive(serde::Deserialize, Debug)]
struct TradeMessage {
    header: Header,
    contract: Contract,
    trade: Trade,
}

pub async fn handle_msg(msg: Message) {
    // TODO determine if status or quote or trade message
    let Ok(text) = msg.into_text() else {
        log::error!("Err while parsing Message into text");
        return;
    };
    log::debug!("Received message: {}", text);

    let Ok(v): Result<serde_json::Value, _> = serde_json::from_str(&text) else {
        log::error!("Err while deserializing");
        return;
    };

    // Since the message type is not top level, we have to manually descide what to deserialize into
    // TODO don't unwrap
    let message: MessageType = match v["header"]["type"].as_str() {
        Some("STATUS") => MessageType::Status(serde_json::from_value(v).unwrap()),
        Some("STATE") => MessageType::State(serde_json::from_value(v).unwrap()),
        Some("REQ_RESPONSE") => MessageType::ReqResponse(serde_json::from_value(v).unwrap()),
        Some("QUOTE") => MessageType::Quote(serde_json::from_value(v).unwrap()),
        Some("TRADE") => MessageType::Trade(serde_json::from_value(v).unwrap()),
        other => { log::warn!("Unexpected type value in message header: {:?}", other); log::warn!("Unexpected message: {}", v); return }
    };
    match message {
        MessageType::Quote(m) => log::info!("{:?}", m),
        _ => return
    }
}


pub async fn ingest(ws_url: String, contracts: Vec<ContractSubscribe>, token: CancellationToken) {
    let (ws_stream, _) = connect_async(&ws_url).await.expect("Failed to connect to theta data terminal");
    log::info!("WebSocket handshake has been successfully completed");

    let (mut write, mut read) = ws_stream.split();

    // Clear all prior subscriptions
    let stop_payload = "
        {
            \"msg_type\": \"STOP\"
        }";
    write.send(Message::Text(stop_payload.into())).await.expect("Failed to send payload");

    // Subscribe to current contracts
    let mut num_subscribed = 0;
    for (idx, contract) in contracts.iter().enumerate() {
        let root = &contract.root;
        let expiration = &contract.expiration;
        let right = &contract.right;
        let strike = &contract.strike;

        let payload = format!("
            {{
                \"msg_type\": \"STREAM\",
                \"sec_type\": \"OPTION\",
                \"req_type\": \"QUOTE\",
                \"add\": true,
                \"id\": {idx},
                \"contract\": {{
                    \"root\": \"{root}\",
                    \"expiration\": \"{expiration}\",
                    \"strike\": {strike},
                    \"right\": \"{right}\"
                }}
            }}");
        write.send(Message::Text(payload.into())).await.expect("Failed to send payload");
        num_subscribed += 1;
    }
    log::info!("Subscribed to {} contracts", num_subscribed);

    // Race between message received and ctrl-c
    loop {
        tokio::select! {
            _ = token.cancelled() => {
                write.send(Message::Text(stop_payload.into())).await.expect("Failed to send payload");
                log::info!("Stopped all streams");
                break;
            }
            msg = read.next() => {
                match msg {
                    Some(Ok(m)) => handle_msg(m).await,
                    Some(Err(e)) => log::error!("WebSocket error: {}", e),
                    None => break
                }
            }
        }
    }
}
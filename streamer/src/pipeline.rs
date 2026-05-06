use csv_async::AsyncReaderBuilder;
use tokio::net::TcpStream;
use tokio_util::io::StreamReader;
use futures_util::{StreamExt, SinkExt, stream::SplitSink, stream::SplitStream};
use futures::TryStreamExt;
use std::io;
use tokio_tungstenite::{MaybeTlsStream, WebSocketStream, tungstenite::protocol::Message};

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
        let right = match r.right == "Call" {
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
                    contracts.push(contract_response.into());
                }
            
            if let Some(next_page) = headers.get("Next-Page") {
                match next_page.to_str() {
                    Ok(s) => url = s.to_string(),
                    Err(_) => break
                }
            } else {
                break
            }
        }
    }
    
    Ok(contracts)
}

pub async fn ingest(mut read: SplitStream<WebSocketStream<MaybeTlsStream<TcpStream>>>, mut write: SplitSink<WebSocketStream<MaybeTlsStream<TcpStream>>, Message>, contracts: Vec<ContractSubscribe>) {
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
                \"req_type\": \"TRADE\",
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

    while let Some(msg) = read.next().await {
        log::info!("{:?}", msg);
    }

}
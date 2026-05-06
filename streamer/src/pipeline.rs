use csv_async::AsyncReaderBuilder;
use tokio::net::TcpStream;
use tokio_util::io::StreamReader;
use futures_util::{StreamExt, SinkExt, stream::SplitSink};
use futures::TryStreamExt;
use std::io;
use tokio_tungstenite::{MaybeTlsStream, WebSocketStream, tungstenite::protocol::Message};

#[derive(serde::Deserialize, Debug)]
pub struct ContractResponse {
    symbol: String,
    expiration: String,
    strike: f64,
    right: String,
}

pub async fn fetch_contracts(http_base: &str) -> Result<Vec<ContractResponse>, Box<dyn std::error::Error>> {
    // Fetch all active SPX/SPXW option contracts from the list contracts endpoint.
    // 
    // Response is streamed CSV: "SPX","2026-03-20",6475.000,"CALL"
    // Converted to subscription format: {root, expiration (YYYYMMDD int), strike (1/10th cent int), right (C/P)}
    
    // TODO add SPXW contracts up to 10k contracts total

    let mut url = format!("{http_base}/v3/option/list/contracts/quote?symbol=SPX&date=20250428");
    let mut contracts: Vec<ContractResponse> = Vec::new();
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
                    contracts.push(contract_response);
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

pub async fn ingest(mut write: SplitSink<WebSocketStream<MaybeTlsStream<TcpStream>>, Message>, contracts: Vec<ContractResponse>) {
    // TODO subscribe to all contracts
    for (idx, contract) in contracts.iter().enumerate() {
        log::info!("{:?}", contract);

        // TODO incrememnt id for separate streams
        let expiration = &contract.expiration;
        let right = &contract.right;
        let payload = format!("
            {{
                \"msg_type\": \"STREAM\",
                \"sec_type\": \"OPTION\",
                \"req_type\": \"TRADE\",
                \"add\": true,
                \"id\": {idx},
                \"contract\": {{
                    \"root\": \"SPX\",
                    \"expiration\": \"{expiration}\",
                    \"strike\": 7250000,
                    \"right\": \"{right}\"
                }}
            }}");
        write.send(Message::Text(payload.into())).await.expect("Failed to send payload");
    }
}
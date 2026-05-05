use csv_async::AsyncReaderBuilder;
use tokio_util::io::StreamReader;
use futures_util::StreamExt;
use futures::TryStreamExt;
use std::io;

#[derive(serde::Deserialize, Debug)]
struct QuoteResponse {
    symbol: String,
    expiration: String,
    strike: f64,
    right: String,
}

pub async fn fetch_contracts(http_base: &str) -> Result<(), Box<dyn std::error::Error>> {
    // Fetch all active SPX/SPXW option contracts from the list contracts endpoint.
    // 
    // Response is streamed CSV: "SPX","2026-03-20",6475.000,"CALL"
    // Converted to subscription format: {symbol, expiration (YYYYMMDD int), strike (1/10th cent int), right (C/P)}
    
    let url = format!("{http_base}/v3/option/list/contracts/quote?symbol=SPX&date=20250428");
    let response = reqwest::get(url).await?;
    log::info!("{:?}", response);
    let stream = response.bytes_stream().map_err(|e| io::Error::new(io::ErrorKind::Other, e));
    let stream_reader = StreamReader::new(stream);
    let mut async_reader = AsyncReaderBuilder::new().create_deserializer(stream_reader);
    let mut records = async_reader.deserialize::<QuoteResponse>();

    while let Some(record) = records.next().await {
        match record {
            Ok(data) => log::info!("{:?}", data),
            Err(e) => log::error!("deserialization error: {}", e),
        }
    }
    
    Ok(())
}
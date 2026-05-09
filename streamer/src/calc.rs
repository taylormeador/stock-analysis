use tokio::sync::mpsc::Receiver;
use crate::ingest::QuoteMessage;
use tokio;
use tokio_util::sync::CancellationToken;

pub async fn calc_iv(mut iv_rx: Receiver<QuoteMessage>, token: CancellationToken) {
    loop {
        tokio::select! {
            _ = token.cancelled() => {
                break;
            }
            msg = iv_rx.recv() => {
                match msg {
                    Some(m) => log::info!("{:?}", m),
                    None => break
                }
            }
        }
    }
}

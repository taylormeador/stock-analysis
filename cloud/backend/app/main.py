from fastapi import FastAPI
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/")
def index():
    return {"hello": "world"}


@app.get("/health")
def health():
    return {"status": "up"}


@app.get("/sentiment_volume")
def sentiment_volume():
    hours = ["10am", "11am", "12pm", "1pm", "2pm"]
    positive_counts = [30, 45, 40, 60, 55]
    neutral_counts = [20, 15, 25, 20, 25]
    negative_counts = [10, 15, 10, 5, 20]
    data = {
        "hours": hours,
        "positive_counts": positive_counts,
        "neutral_counts": neutral_counts,
        "negative_counts": negative_counts,
    }
    return {"data": data}

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from sqlalchemy import text

from app.celery_app import app
from app.database.db import get_connection

tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")


@app.task
def run_sentiment_analysis():
    text = "Wow this is a great stock. NOT"

    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    outputs = model(**inputs)
    predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

    label = ["negative", "neutral", "positive"][predictions.argmax().item()]  # type: ignore
    confidence = predictions.max().item()

    return label, confidence


if __name__ == "__main__":
    result = run_sentiment_analysis()
    breakpoint()

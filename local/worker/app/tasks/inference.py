# from transformers import AutoTokenizer, AutoModelForSequenceClassification
# import torch
# from sqlalchemy import text

# from app.celery_app import app
# from app.database.db import get_connection

# tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
# model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")


# @app.task
# def run_sentiment_analysis():
#     with get_connection() as db:
#         comments = """
#             select * from reddit comments where id in
#             (select unique(comment_id) from reddit_comments);
#         """

#     inputs = tokenizer(comment, return_tensors="pt", truncation=True, max_length=512)
#     outputs = model(**inputs)
#     predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

#     label = ["negative", "neutral", "positive"][predictions.argmax().item()]  # type: ignore
#     confidence = predictions.max().item()


# if __name__ == "__main__":
#     texts = [
#         "this is oging to the moon",
#         "wow what a great stock",
#         "wow what a great stock, not",
#         "wow! what a great stock!",
#         "LFG",
#     ]
#     results = []
#     for t in texts:
#         result = run_sentiment_analysis(t)
#         results.append(result)
#     breakpoint()

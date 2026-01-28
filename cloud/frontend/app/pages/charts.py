import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
import requests
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

API_URL = os.environ["API_URL"]

logger.info("getting data")
response = requests.get(API_URL + "/sentiment_volume")
data = response.json()["data"]

hours = data["hours"]
positive_counts = data["positive_counts"]
neutral_counts = data["neutral_counts"]
negative_counts = data["negative_counts"]

fig = make_subplots(specs=[[{"secondary_y": True}]])

# Stacked bars for volume
fig.add_trace(go.Bar(name="Positive", x=hours, y=positive_counts, marker_color="green"))
fig.add_trace(go.Bar(name="Neutral", x=hours, y=neutral_counts, marker_color="gray"))
fig.add_trace(go.Bar(name="Negative", x=hours, y=negative_counts, marker_color="red"))

# Line for net sentiment
net_sentiment = [
    (p - n) / (p + n + neu)
    for p, n, neu in zip(positive_counts, negative_counts, neutral_counts)
]
fig.add_trace(
    go.Scatter(
        name="Net Sentiment",
        x=hours,
        y=net_sentiment,
        mode="lines+markers",
        line=dict(color="blue", width=3),
    ),
    secondary_y=True,
)

fig.update_layout(
    barmode="stack",
    title="TSLA Sentiment Volume Over Time",
    xaxis_title="Time",
    yaxis_title="Number of Mentions",
)
fig.update_yaxes(title_text="Volume", secondary_y=False)
fig.update_yaxes(title_text="Net Sentiment", secondary_y=True)

st.plotly_chart(fig)

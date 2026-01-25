import plotly.express as px
import streamlit as st
import pandas as pd

from data import stock_data

df = pd.DataFrame(stock_data)

fig = px.scatter(
    df,
    x="mention_count",
    y="sentiment_score",
    color="ticker",
    size="avg_upvotes",
    hover_data=["timestamp"],
    title="Sentiment vs Mention Volume",
)
st.plotly_chart(fig, use_container_width=True)

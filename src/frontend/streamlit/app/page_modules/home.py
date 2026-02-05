import streamlit as st
from styles import apply_custom_css
from utils import get_json

apply_custom_css()

# Page header
st.title(":material/query_stats: CurveFitter9000")
st.caption("Real-time market analysis and ML insights")
st.divider()

# Welcome section
col1, col2, col3 = st.columns([10, 0.1, 5])

with col1:
    st.markdown(
        """
    ### Welcome to CurveFitter9000
    
    This platform combines **financial market data**, **math**, 
    and **wishful thinking** to provide systematic strategy research and real-time market insights.
    """
    )

    st.subheader(":material/target: Key Features")

    with st.expander(":material/trending_up: Market Data Integration", expanded=True):
        st.markdown(
            """
        - Historical **OHLCV** price data
        - Technical indicators (**RSI**, **MACD**, **Bollinger Bands**)
        - **CBOE** options market data (put/call ratios, volume, OI)
        - **FRED** macroeconomic indicators
        """
        )

    with st.expander(":material/analytics: Sentiment Analysis (In Development)"):
        st.markdown(
            """
        - Real-time tracking of **r/WallStreetBets** discussions
        - Ticker mention frequency and trending analysis
        - Sentiment classification and indicators + more sites like Stocktwits and Twitter
        """
        )

    with st.expander(":material/psychology: Math + Machine Learning"):
        st.markdown(
            """
        - **XGBoost**-based prediction models
        - Feature importance analysis
        - **MLflow** experiment tracking
        - Backtesting framework
        - **Vibes** based insights from Claude LLM
        """
        )

    with st.expander(":material/bolt: Real-time Processing"):
        st.markdown(
            """
        - Distributed **Celery** workers
        - **FastAPI** REST endpoints
        - **Redis**-based caching and rate limiting
        - **PostgreSQL** data persistence
        """
        )

with col3:
    st.markdown(
        "#### :material/trending_up: What's Trending TODO", text_alignment="center"
    )
    # Top 3 tickers from What's Hot page
    # trending_tickers = get_json("/whats-hot")["ticker_mentions"][:3]
    trending = {"TEST": 178, "FOO": 45, "BAR": 32}
    for t in trending.items():
        st.metric(t[0], f"{t[1]} mentions")

    st.markdown("#### :material/engineering: System Health", text_alignment="center")
    status = get_json("/etl-status")

    col_a, col_b, col_c = st.columns([10, 1, 10])
    with col_a:
        st.metric("Active Workers", "3")
        st.metric("Tasks/Hour", status.get("tasks_per_hour", "N/A"))
    with col_c:
        st.metric("Success Rate", "98.5%")
        st.metric("Queue Size", status.get("queue_size", "0"))
st.divider()

st.subheader(":material/layers: Platform Stack")
tab1, tab2, tab3 = st.tabs(
    [
        ":material/storage: Data Pipeline",
        ":material/model_training: ML & Analysis",
        ":material/deployed_code: Deployment",
    ]
)

with tab1:
    st.markdown(
        """
    **Collection** → Reddit JSON endpoints, yfinance, CBOE, FRED   
    **Storage** → PostgreSQL, Redis, S3   
    **Processing** → Celery workers, distributed rate limiting   
    """
    )

with tab2:
    st.markdown(
        """
    **Models** → FinBERT sentiment, XGBoost predictions   
    **Features** → Macroeconomic data, options market flows, pandas-ta   
    **Tracking** → MLflow experiments, backtesting framework   
    """
    )

with tab3:
    st.markdown(
        """
    **Infrastructure** → Docker on Debian on Proxmox Virtual Environment   
    **API** → FastAPI with async SQLAlchemy  
    **Frontend** → Streamlit + nginx reverse proxy
    """
    )


# Sidebar
st.sidebar.markdown("### :material/info: System Status TODO")
st.sidebar.success("**SYSTEM:** OPERATIONAL")
st.sidebar.caption("**DATA REFRESH:** 2-5 MIN | **SENTIMENT:** REAL-TIME")

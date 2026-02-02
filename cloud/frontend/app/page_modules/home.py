import streamlit as st
from styles import apply_custom_css

apply_custom_css()

# Page header
st.title(":material/analytics: CurveFitter9000")
st.caption("Real-time market analysis and ML insights")
st.divider()

# Welcome section
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(
        """
    ### Welcome to CurveFitter9000
    
    This platform combines **financial market data**, **math**, 
    and **wishful thinking** to provide systematic strategy research and real-time market insights.
    """
    )

    st.subheader(":material/target: Key Features")

    with st.expander(":material/analytics: Sentiment Analysis", expanded=True):
        st.markdown(
            """
        - Real-time tracking of **r/WallStreetBets** discussions
        - Ticker mention frequency and trending analysis
        - \*In Development\* Sentiment classification and indicators + more sites like Stocktwits and Twitter
        """
        )

    with st.expander(":material/trending_up: Market Data Integration"):
        st.markdown(
            """
        - Historical **OHLCV** price data
        - Technical indicators (**RSI**, **MACD**, **Bollinger Bands**)
        - **CBOE** options market data (put/call ratios, volume, OI)
        - **FRED** macroeconomic indicators
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

with col2:
    st.info(
        ":material/rocket_launch: **Quick Start**\n\nNavigate using the sidebar to explore different sections of the platform."
    )

    st.success(
        ":material/trending_up: **What's Hot**\n\nView trending tickers and sentiment from WSB daily discussions."
    )

    st.warning(
        ":material/settings: **ETL Status**\n\nMonitor the health and status of data pipelines."
    )

st.divider()

# Architecture
st.subheader(":material/architecture: System Architecture")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### :material/download: DATA COLLECTION")
    st.markdown(
        """
    - **Reddit JSON Endpoints** - Comment scraping
    - **yfinance** - Historical prices
    - **CBOE** - Options market data
    - **FRED** - Macro indicators
    """
    )

with col2:
    st.markdown("#### :material/settings: PROCESSING")
    st.markdown(
        """
    - **Celery** - Distributed tasks
    - **FinBERT** - Sentiment analysis
    - **pandas-ta** - Technical indicators
    - **PostgreSQL** - Data storage
    """
    )

with col3:
    st.markdown("#### :material/analytics: ANALYSIS")
    st.markdown(
        """
    - **XGBoost** - ML predictions
    - **MLflow** - Experiment tracking
    - **Backtesting** - Strategy validation
    - **Streamlit** - Visualization
    """
    )

st.divider()

# Tech stack
st.subheader(":material/code: Technology Stack")

tab1, tab2, tab3 = st.tabs(
    [
        ":material/database: Data Layer",
        ":material/psychology: ML Stack",
        ":material/web: Frontend",
    ]
)

with tab1:
    st.markdown(
        """
    **Database & Storage**
    - **PostgreSQL** - Primary data store
    - **Redis** - Caching and task queue
    - **S3** - Data lake and artifacts
    
    **Data Sources**
    - **Reddit API** (PRAW)
    - **yfinance** (market data)
    - **CBOE** (options data)
    - **FRED** (macroeconomic data)
    """
    )

with tab2:
    st.markdown(
        """
    **Models & Libraries**
    - **Transformers** (FinBERT)
    - **XGBoost**, **LightGBM**
    - **scikit-learn**
    - **pandas**, **numpy**
    
    **ML Infrastructure**
    - **MLflow** - Experiment tracking
    - **pandas-ta** - Technical analysis
    - Backtesting framework
    """
    )

with tab3:
    st.markdown(
        """
    **Application**
    - **Streamlit** - Dashboard framework
    - **Plotly** - Interactive charts
    - **FastAPI** - Backend API
    
    **Infrastructure**
    - **Docker** - Containerization
    - **nginx** - Reverse proxy
    - **Celery** - Task orchestration
    """
    )

st.divider()

# System status
st.subheader(":material/monitor_heart: System Status")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label=":material/forum: Comments Analyzed", value="12,453", delta="142 today"
    )

with col2:
    st.metric(
        label=":material/show_chart: Tickers Tracked", value="187", delta="99.8% uptime"
    )

with col3:
    st.metric(label=":material/psychology: ML Models", value="3", delta="0.67 Sharpe")

# Sidebar
st.sidebar.markdown("### :material/info: System Status")
st.sidebar.success("**SYSTEM:** OPERATIONAL")
st.sidebar.caption("**DATA REFRESH:** 2-5 MIN | **SENTIMENT:** REAL-TIME")

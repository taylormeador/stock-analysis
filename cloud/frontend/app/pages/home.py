import streamlit as st
from styles import create_header, create_info_box, create_subheader

# Page header
create_header(
    "Stock Analysis Platform 📈", "Real-time sentiment analysis and market insights"
)

# Welcome section
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(
        """
        ### Welcome to Your Quantitative Trading Platform
        
        This platform combines **Reddit sentiment analysis**, **financial market data**, 
        and **machine learning** to provide systematic strategy research and real-time market insights.
        
        #### 🎯 Key Features
        
        **📊 Sentiment Analysis**
        - Real-time tracking of r/WallStreetBets discussions
        - FinBERT-powered sentiment classification
        - Ticker mention frequency and trending analysis
        
        **💹 Market Data Integration**
        - Historical OHLC price data
        - Technical indicators (RSI, MACD, Bollinger Bands)
        - CBOE options market data (put/call ratios, volume, OI)
        - FRED macroeconomic indicators
        
        **🤖 Machine Learning**
        - XGBoost-based prediction models
        - Feature importance analysis
        - MLflow experiment tracking
        - Backtesting framework
        
        **⚡ Real-time Processing**
        - Distributed Celery workers
        - Redis-based rate limiting
        - PostgreSQL data persistence
        - S3-backed data layer
        """
    )

with col2:
    create_info_box(
        "🚀 Quick Start",
        "Navigate using the sidebar to explore different sections of the platform.",
        box_type="info",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    create_info_box(
        "📈 What's Hot",
        "View trending tickers and sentiment from WSB daily discussions.",
        box_type="success",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    create_info_box(
        "⚙️ ETL Status",
        "Monitor the health and status of data pipelines.",
        box_type="warning",
    )

st.markdown("<br><br>", unsafe_allow_html=True)

# Architecture overview
create_subheader("System Architecture")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div class="card">
            <h4 style="color: #00d4aa; margin-top: 0;">📥 Data Collection</h4>
            <ul style="color: #fafafa;">
                <li>Reddit API scraping</li>
                <li>yfinance price data</li>
                <li>CBOE options data</li>
                <li>FRED macro indicators</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div class="card">
            <h4 style="color: #00d4aa; margin-top: 0;">⚙️ Processing</h4>
            <ul style="color: #fafafa;">
                <li>Sentiment analysis (FinBERT)</li>
                <li>Technical indicators</li>
                <li>Feature engineering</li>
                <li>Model training</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
        <div class="card">
            <h4 style="color: #00d4aa; margin-top: 0;">📊 Analysis</h4>
            <ul style="color: #fafafa;">
                <li>Trend detection</li>
                <li>Signal generation</li>
                <li>Backtesting</li>
                <li>Performance metrics</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# Technology stack
create_subheader("Technology Stack")

tech_col1, tech_col2 = st.columns(2)

with tech_col1:
    st.markdown(
        """
        **Backend & Processing**
        - 🐍 Python 3.13
        - 🔄 Celery (distributed workers)
        - 🗄️ PostgreSQL (data storage)
        - 📦 Redis (caching & coordination)
        - 🤖 Transformers (FinBERT)
        """
    )

with tech_col2:
    st.markdown(
        """
        **ML & Analytics**
        - 📊 XGBoost, LightGBM
        - 🧪 MLflow (experiment tracking)
        - 📈 pandas-ta (technical analysis)
        - 🎨 Plotly (visualization)
        - ☁️ AWS S3 (data layer)
        """
    )

# Footer
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(
    """
    <div style="text-align: center; color: #a0a0a0; padding: 2rem; border-top: 1px solid #2a2e3a;">
        <p>Built for systematic strategy research and alpha discovery 🚀</p>
        <p style="font-size: 0.9rem;">Data updates every 2-5 minutes | Real-time sentiment analysis</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar
st.sidebar.markdown("### 🎯 Navigation")
st.sidebar.info(
    """
    Use the navigation menu to explore:
    - **Home**: Platform overview
    - **What's Hot**: Trending tickers
    - **ETL Status**: Pipeline health
    """
)

st.sidebar.markdown("### 📊 System Status")
st.sidebar.success("✅ All systems operational")

st.sidebar.markdown("### 💡 Tips")
st.sidebar.markdown(
    """
    - Check **What's Hot** for real-time WSB trends
    - Monitor **ETL Status** for data pipeline health
    - Data refreshes automatically
    """
)

import streamlit as st
import streamlit.components.v1 as components
from styles import apply_custom_css

apply_custom_css()

st.title(":material/terminal: MAINFRAME")
st.caption("config_version==0x5b59flk")
st.divider()


hacker_html = """
<!DOCTYPE html>
<html>
<head>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background-color: #0d1117; color: #00FF41; font-family: 'Courier New', monospace; overflow: hidden; height: 100vh; }
        #terminal { padding: 20px; height: 100vh; overflow-y: auto; font-size: 14px; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; }
        #cursor { display: inline-block; width: 10px; height: 18px; background-color: #00FF41; animation: blink 1s infinite; vertical-align: text-bottom; }
        @keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
        ::-webkit-scrollbar { width: 10px; }
        ::-webkit-scrollbar-track { background: #0d1117; }
        ::-webkit-scrollbar-thumb { background: #00FF41; box-shadow: 0 0 5px #00FF41; }
    </style>
</head>
<body>
    <div id="terminal"><span id="cursor"></span></div>
    <script>
        const code = `#!/usr/bin/env python3
# Stock Analysis Trading Bot - ML Pipeline
# Classification: CONFIDENTIAL

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from datetime import datetime, timedelta
import logging
import asyncio

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('TradingBot')

class SentimentAnalyzer:
    def __init__(self, model_path='/models/finbert'):
        self.model_path = model_path
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        logger.info(f"Initializing SentimentAnalyzer on {self.device}")
        self.model = self._load_model()
        
    def _load_model(self):
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        logger.debug("Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        logger.debug("Loading model weights...")
        model = AutoModelForSequenceClassification.from_pretrained(self.model_path)
        model.to(self.device)
        logger.info("Model loaded successfully")
        return {'model': model, 'tokenizer': tokenizer}
    
    def analyze_batch(self, texts):
        logger.debug(f"Analyzing batch of {len(texts)} texts")
        inputs = self.model['tokenizer'](texts, padding=True, truncation=True, max_length=512, return_tensors='pt').to(self.device)
        with torch.no_grad():
            outputs = self.model['model'](**inputs)
            scores = torch.softmax(outputs.logits, dim=-1)
        sentiment_scores = scores[:, 2] - scores[:, 0]
        logger.debug(f"Mean sentiment: {sentiment_scores.mean():.3f}")
        return sentiment_scores.cpu().numpy()


class TechnicalIndicators:
    @staticmethod
    def calculate_rsi(prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(prices, fast=12, slow=26, signal=9):
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return {'macd': macd, 'signal': signal_line, 'histogram': histogram}


class PortfolioOptimizer:
    def __init__(self, risk_free_rate=0.02):
        self.risk_free_rate = risk_free_rate
        logger.info("Initializing Portfolio Optimizer")
    
    def optimize_weights(self, returns, target_return=None):
        from scipy.optimize import minimize
        n_assets = len(returns.columns)
        
        def portfolio_stats(weights):
            portfolio_return = np.sum(returns.mean() * weights) * 252
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(returns.cov() * 252, weights)))
            sharpe = (portfolio_return - self.risk_free_rate) / portfolio_std
            return portfolio_return, portfolio_std, sharpe
        
        def neg_sharpe(weights):
            return -portfolio_stats(weights)[2]
        
        constraints = {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        bounds = tuple((0, 1) for _ in range(n_assets))
        init_weights = np.array([1/n_assets] * n_assets)
        
        logger.debug("Running optimization...")
        result = minimize(neg_sharpe, init_weights, method='SLSQP', bounds=bounds, constraints=constraints)
        
        optimal_weights = result.x
        ret, std, sharpe = portfolio_stats(optimal_weights)
        logger.info(f"Optimized - Return: {ret:.2%}, Volatility: {std:.2%}, Sharpe: {sharpe:.3f}")
        return optimal_weights


class RiskManager:
    def __init__(self, max_position_size=0.1, max_drawdown=0.15):
        self.max_position_size = max_position_size
        self.max_drawdown = max_drawdown
        self.positions = {}
        logger.info("Risk Manager initialized")
    
    def calculate_position_size(self, signal_strength, account_value, volatility):
        win_rate = 0.5 + (signal_strength * 0.3)
        win_loss_ratio = 1.5
        kelly_fraction = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        volatility_scalar = min(1.0, 0.2 / volatility)
        position_size = kelly_fraction * volatility_scalar * account_value
        position_size = min(position_size, self.max_position_size * account_value)
        logger.debug(f"Position size: {position_size:,.2f}")
        return position_size


async def fetch_market_data(symbols, start_date, end_date):
    import yfinance as yf
    logger.info(f"Fetching data for {len(symbols)} symbols")
    data = {}
    for symbol in symbols:
        logger.debug(f"Downloading {symbol}...")
        df = yf.download(symbol, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        data[symbol] = df
        await asyncio.sleep(0.1)
    logger.info("Data fetch complete")
    return data


class MLPredictor:
    def __init__(self):
        self.models = {
            'rf': RandomForestClassifier(n_estimators=100, max_depth=10),
            'gb': GradientBoostingRegressor(n_estimators=100, learning_rate=0.1)
        }
        self.fitted = False
        logger.info("ML Predictor initialized")
    
    def train(self, X_train, y_train):
        logger.info("Training models...")
        for name, model in self.models.items():
            logger.debug(f"Training {name}...")
            model.fit(X_train, y_train)
        self.fitted = True
        logger.info("Training complete")
    
    def predict(self, X):
        if not self.fitted:
            raise ValueError("Models must be trained before prediction")
        predictions = []
        for name, model in self.models.items():
            pred = model.predict(X)
            predictions.append(pred)
        ensemble_pred = np.mean(predictions, axis=0)
        return ensemble_pred


async def main():
    logger.info("=" * 60)
    logger.info("INITIALIZING TRADING SYSTEM")
    logger.info("=" * 60)
    
    sentiment_analyzer = SentimentAnalyzer()
    portfolio_optimizer = PortfolioOptimizer()
    risk_manager = RiskManager()
    ml_predictor = MLPredictor()
    
    symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA']
    logger.info(f"Trading universe: {', '.join(symbols)}")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    market_data = await fetch_market_data(symbols, start_date, end_date)
    
    logger.info("System ready. Entering trading loop...")
    
    while True:
        try:
            logger.info("Processing market data...")
            await asyncio.sleep(60)
        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    logger.info("Starting Stock Analysis Trading Bot v2.1")
    asyncio.run(main())
`;

        let currentIndex = 0;
        const terminal = document.getElementById('terminal');
        const cursor = document.getElementById('cursor');
        
        function addText() {
            if (currentIndex < code.length) {
                const char = code[currentIndex];
                const textNode = document.createTextNode(char);
                terminal.insertBefore(textNode, cursor);
                currentIndex++;
                terminal.scrollTop = terminal.scrollHeight;
            }
        }
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Backspace') {
                terminal.innerHTML = '<span id="cursor"></span>';
                currentIndex = 0;
                return;
            }
            for (let i = 0; i < 3; i++) { addText(); }
        });
        
        window.addEventListener('load', function() { document.body.focus(); });
    </script>
</body>
</html>
"""

components.html(hacker_html, height=600, scrolling=False)

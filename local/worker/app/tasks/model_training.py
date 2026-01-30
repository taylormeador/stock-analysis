"""
Model training script with MLFlow experiment tracking.

This script trains prediction models on prepared data and logs all experiments
to MLFlow for comparison and model versioning.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error
from xgboost import XGBRegressor

from app.celery_app import app

logger = logging.getLogger(__name__)

# MLFlow configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)


def calculate_trading_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Calculate trading-relevant metrics beyond standard regression metrics.

    Args:
        y_true: Actual forward returns
        y_pred: Predicted forward returns

    Returns:
        Dictionary of trading metrics
    """
    # Directional accuracy (did we predict the right direction?)
    direction_correct = np.mean(np.sign(y_pred) == np.sign(y_true))

    # Strategy returns (if we traded based on predictions)
    # Long when prediction > 0, short when < 0
    strategy_returns = y_true * np.sign(y_pred)

    # Sharpe ratio (annualized, assuming daily returns)
    sharpe = (
        np.mean(strategy_returns) / np.std(strategy_returns) * np.sqrt(252)
        if np.std(strategy_returns) > 0
        else 0
    )

    # Win rate (what % of trades were profitable)
    win_rate = np.mean(strategy_returns > 0)

    # Max drawdown
    cumulative_returns = np.cumprod(1 + strategy_returns)
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdown = (cumulative_returns - running_max) / running_max
    max_drawdown = np.min(drawdown)

    # Profit factor (gross profits / gross losses)
    profits = strategy_returns[strategy_returns > 0].sum()
    losses = abs(strategy_returns[strategy_returns < 0].sum())
    profit_factor = profits / losses if losses > 0 else 0

    return {
        "direction_accuracy": direction_correct,
        "sharpe_ratio": sharpe,
        "win_rate": win_rate,
        "max_drawdown": max_drawdown,
        "profit_factor": profit_factor,
        "total_return": cumulative_returns[-1] - 1,
        "avg_return_per_trade": np.mean(strategy_returns),
    }


@app.task
def train_xgboost_model(
    training_data_path: str,
    experiment_name: str = "stock_prediction_v1",
    run_name: str | None = None,
    features: list[str] | None = None,
    model_params: dict | None = None,
    train_end_date: str = "2023-01-01",
) -> dict:
    """
    Train an XGBoost model and log to MLFlow.

    Args:
        training_data_path: Path to parquet file with training data
        experiment_name: MLFlow experiment name
        run_name: Optional custom name for this run
        features: List of feature column names (defaults to sentiment + TA)
        model_params: XGBoost hyperparameters
        train_end_date: Split point between train and test sets

    Returns:
        Dictionary with metrics and model info
    """
    logger.info(f"Training XGBoost model with data from {training_data_path}")

    # Set MLFlow experiment
    mlflow.set_experiment(experiment_name)

    # Load data
    df = pd.read_parquet(training_data_path)
    logger.info(f"Loaded {len(df)} rows from {training_data_path}")

    # Default features if not specified
    if features is None:
        features = [
            "sentiment_score",
            "mention_count",
            "avg_confidence",
            "positive_count",
            "negative_count",
            "rsi_14",
            "macd_12_26_9",
            "volume",
        ]

    # Filter to only include rows where all features are available
    df_clean = df.dropna(subset=features + ["forward_1d_return"])
    logger.info(f"After dropping NaNs: {len(df_clean)} rows")

    # Convert train_end_date string to date object for comparison
    from datetime import datetime

    if isinstance(train_end_date, str):
        train_end_date = datetime.strptime(train_end_date, "%Y-%m-%d").date()

    # Temporal train/test split
    train = df_clean[df_clean["date"] < train_end_date]
    test = df_clean[df_clean["date"] >= train_end_date]

    logger.info(
        f"Train set: {len(train)} rows ({train['date'].min()} to {train['date'].max()})"
    )
    logger.info(
        f"Test set: {len(test)} rows ({test['date'].min()} to {test['date'].max()})"
    )

    X_train, y_train = train[features], train["forward_1d_return"]
    X_test, y_test = test[features], test["forward_1d_return"]

    # Default model parameters
    if model_params is None:
        model_params = {
            "n_estimators": 100,
            "max_depth": 5,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }

    # Generate run name
    if run_name is None:
        run_name = f"xgb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Start MLFlow run
    with mlflow.start_run(run_name=run_name):
        logger.info(f"Started MLFlow run: {run_name}")

        # Log parameters
        mlflow.log_params(model_params)
        mlflow.log_param("features", features)
        mlflow.log_param("train_start", str(train["date"].min()))
        mlflow.log_param("train_end", str(train["date"].max()))
        mlflow.log_param("test_start", str(test["date"].min()))
        mlflow.log_param("test_end", str(test["date"].max()))
        mlflow.log_param("train_size", len(train))
        mlflow.log_param("test_size", len(test))

        # Train model
        logger.info("Training model...")
        model = XGBRegressor(**model_params)
        model.fit(X_train, y_train)

        # Predictions
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)

        # Regression metrics
        train_mse = mean_squared_error(y_train, train_pred)
        test_mse = mean_squared_error(y_test, test_pred)
        train_mae = mean_absolute_error(y_train, train_pred)
        test_mae = mean_absolute_error(y_test, test_pred)

        mlflow.log_metric("train_mse", train_mse)
        mlflow.log_metric("test_mse", test_mse)
        mlflow.log_metric("train_mae", train_mae)
        mlflow.log_metric("test_mae", test_mae)

        # Trading metrics
        train_trading_metrics = calculate_trading_metrics(y_train.values, train_pred)
        test_trading_metrics = calculate_trading_metrics(y_test.values, test_pred)

        # Log trading metrics with train/test prefix
        for metric_name, value in train_trading_metrics.items():
            mlflow.log_metric(f"train_{metric_name}", value)

        for metric_name, value in test_trading_metrics.items():
            mlflow.log_metric(f"test_{metric_name}", value)

        logger.info(f"Test Sharpe Ratio: {test_trading_metrics['sharpe_ratio']:.3f}")
        logger.info(
            f"Test Direction Accuracy: {test_trading_metrics['direction_accuracy']:.3f}"
        )
        logger.info(f"Test Win Rate: {test_trading_metrics['win_rate']:.3f}")

        # Feature importance plot
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 6))
        feature_importance = pd.Series(
            model.feature_importances_, index=features
        ).sort_values(ascending=False)
        feature_importance.plot(kind="barh", ax=ax)
        ax.set_title("Feature Importance")
        ax.set_xlabel("Importance")
        plt.tight_layout()
        mlflow.log_figure(fig, "feature_importance.png")
        plt.close()

        # Prediction vs actual scatter plot
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        ax1.scatter(y_train, train_pred, alpha=0.3, s=1)
        ax1.plot(
            [y_train.min(), y_train.max()],
            [y_train.min(), y_train.max()],
            "r--",
            lw=2,
        )
        ax1.set_xlabel("Actual Return")
        ax1.set_ylabel("Predicted Return")
        ax1.set_title(f"Train Set (MSE: {train_mse:.6f})")

        ax2.scatter(y_test, test_pred, alpha=0.3, s=1)
        ax2.plot(
            [y_test.min(), y_test.max()],
            [y_test.min(), y_test.max()],
            "r--",
            lw=2,
        )
        ax2.set_xlabel("Actual Return")
        ax2.set_ylabel("Predicted Return")
        ax2.set_title(f"Test Set (MSE: {test_mse:.6f})")

        plt.tight_layout()
        mlflow.log_figure(fig, "predictions_vs_actual.png")
        plt.close()

        # Log model
        mlflow.sklearn.log_model(model, "model")

        # Get run ID for reference
        run_id = mlflow.active_run().info.run_id
        logger.info(f"MLFlow run ID: {run_id}")

        return {
            "run_id": run_id,
            "test_sharpe": test_trading_metrics["sharpe_ratio"],
            "test_direction_accuracy": test_trading_metrics["direction_accuracy"],
            "test_win_rate": test_trading_metrics["win_rate"],
            "test_mse": test_mse,
        }


if __name__ == "__main__":
    # Example: Train a model locally
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # This assumes you've already generated training data
    training_data_path = "/data/training/fake_training_data.parquet"

    if Path(training_data_path).exists():
        results = train_xgboost_model(
            training_data_path=training_data_path,
            experiment_name="stock_prediction_dev",
            run_name="initial_test",
        )
        print(f"Training complete: {results}")
    else:
        print(f"Training data not found at {training_data_path}")
        print("Run generate_fake_training_data() first")

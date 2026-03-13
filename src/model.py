"""
model.py – Train, evaluate, and persist a stock price prediction model.

Uses a Random Forest Regressor from scikit-learn.  The model is saved to
models/saved_models/ so it can be loaded by predictor.py without retraining.
"""

import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

SAVED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "saved_models")


def train_model(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
    n_estimators: int = 100,
    random_state: int = 42,
) -> tuple:
    """
    Train a Random Forest Regressor and return the fitted model together with
    evaluation metrics.

    Parameters
    ----------
    X : pd.DataFrame
        Feature matrix.
    y : pd.Series
        Target vector (future closing price).
    test_size : float
        Fraction of data held out for evaluation (default 0.2).
    n_estimators : int
        Number of trees in the forest (default 100).
    random_state : int
        Random seed for reproducibility.

    Returns
    -------
    tuple[RandomForestRegressor, StandardScaler, dict]
        ``(model, scaler, metrics)`` where *metrics* is a dict with keys
        ``mae``, ``rmse``, and ``r2``.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, shuffle=False
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = RandomForestRegressor(
        n_estimators=n_estimators, random_state=random_state, n_jobs=-1
    )
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)
    metrics = {
        "mae": mean_absolute_error(y_test, y_pred),
        "rmse": np.sqrt(mean_squared_error(y_test, y_pred)),
        "r2": r2_score(y_test, y_pred),
    }

    return model, scaler, metrics


def save_model(model: RandomForestRegressor, scaler: StandardScaler, ticker: str) -> str:
    """
    Persist the trained model and scaler to ``models/saved_models/``.

    Both objects are saved in a single ``.pkl`` file as a dict so that the
    predictor can reload them together.

    Returns
    -------
    str
        Path to the saved file.
    """
    os.makedirs(SAVED_MODELS_DIR, exist_ok=True)
    filepath = os.path.join(SAVED_MODELS_DIR, f"{ticker}_model.pkl")
    joblib.dump({"model": model, "scaler": scaler}, filepath)
    return filepath


def load_model(ticker: str) -> tuple:
    """
    Load a previously saved model and scaler for *ticker*.

    Returns
    -------
    tuple[RandomForestRegressor, StandardScaler]
    """
    filepath = os.path.join(SAVED_MODELS_DIR, f"{ticker}_model.pkl")
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"No saved model found for ticker '{ticker}' at {filepath}. "
            "Run in --mode train first."
        )
    bundle = joblib.load(filepath)
    return bundle["model"], bundle["scaler"]

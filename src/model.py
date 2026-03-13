"""
model.py – Train, evaluate, and persist stock price prediction models.

Supports Random Forest, XGBoost, and Linear Regression.  Models are saved to
models/saved_models/ so they can be loaded by predictor.py without retraining.
"""

import os
import json
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

SAVED_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "saved_models")

SUPPORTED_MODELS = ["random_forest", "xgboost", "linear_regression"]


def build_model(model_type: str = "random_forest", n_estimators: int = 100, random_state: int = 42):
    """
    Create and return an untrained scikit-learn–compatible model.

    Parameters
    ----------
    model_type : str
        One of ``"random_forest"``, ``"xgboost"``, or ``"linear_regression"``.
    n_estimators : int
        Number of trees for Random Forest / XGBoost (ignored for Linear Regression).
    random_state : int
        Random seed for reproducibility.

    Returns
    -------
    Estimator
        An untrained model instance.
    """
    if model_type == "random_forest":
        return RandomForestRegressor(n_estimators=n_estimators, random_state=random_state, n_jobs=-1)
    elif model_type == "xgboost":
        return XGBRegressor(n_estimators=n_estimators, random_state=random_state, verbosity=0)
    elif model_type == "linear_regression":
        return LinearRegression()
    else:
        raise ValueError(
            f"Unknown model type '{model_type}'. Choose from: {SUPPORTED_MODELS}"
        )


def _compute_metrics(y_true, y_pred) -> dict:
    """Return a dict with MAE, RMSE, and R² for *y_pred* against *y_true*."""
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
    }


def walk_forward_validation(
    X: pd.DataFrame,
    y: pd.Series,
    model_type: str = "random_forest",
    n_splits: int = 5,
    n_estimators: int = 100,
    random_state: int = 42,
) -> dict:
    """
    Evaluate a model using time-series walk-forward cross-validation.

    Each fold trains on past data and tests on the immediately following
    window, which is the correct evaluation strategy for time series.

    Parameters
    ----------
    X : pd.DataFrame
        Feature matrix (must be time-ordered).
    y : pd.Series
        Target vector.
    model_type : str
        Model type to evaluate (same choices as :func:`build_model`).
    n_splits : int
        Number of cross-validation folds (default 5).
    n_estimators : int
        Trees for RF / XGBoost.
    random_state : int
        Random seed.

    Returns
    -------
    dict
        Mean and standard deviation of MAE, RMSE, and R² across all folds,
        keyed as ``cv_mae_mean``, ``cv_mae_std``, etc.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_metrics = []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        model = build_model(model_type, n_estimators=n_estimators, random_state=random_state)
        model.fit(X_train_scaled, y_train)
        y_pred = model.predict(X_test_scaled)

        fold_metrics.append(_compute_metrics(y_test, y_pred))

    cv_metrics = {}
    for metric in ["mae", "rmse", "r2"]:
        values = [m[metric] for m in fold_metrics]
        cv_metrics[f"cv_{metric}_mean"] = float(np.mean(values))
        cv_metrics[f"cv_{metric}_std"] = float(np.std(values))
    return cv_metrics


def train_model(
    X: pd.DataFrame,
    y: pd.Series,
    model_type: str = "random_forest",
    test_size: float = 0.2,
    n_estimators: int = 100,
    random_state: int = 42,
) -> tuple:
    """
    Train a model and return the fitted model together with evaluation metrics.

    Parameters
    ----------
    X : pd.DataFrame
        Feature matrix.
    y : pd.Series
        Target vector (future closing price).
    model_type : str
        One of ``"random_forest"``, ``"xgboost"``, or ``"linear_regression"``.
    test_size : float
        Fraction of data held out for evaluation (default 0.2).
    n_estimators : int
        Number of trees for RF / XGBoost (ignored for Linear Regression).
    random_state : int
        Random seed for reproducibility.

    Returns
    -------
    tuple[estimator, StandardScaler, dict]
        ``(model, scaler, metrics)`` where *metrics* contains keys
        ``mae``, ``rmse``, and ``r2`` from the hold-out test set.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, shuffle=False
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = build_model(model_type, n_estimators=n_estimators, random_state=random_state)
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)
    metrics = _compute_metrics(y_test, y_pred)

    return model, scaler, metrics


def save_model(model, scaler: StandardScaler, ticker: str, model_type: str = "random_forest", horizon: int = 1) -> str:
    """
    Persist the trained model and scaler to ``models/saved_models/``.

    The filename encodes the ticker, model type, and forecast horizon so
    multiple models for the same stock can coexist.

    Returns
    -------
    str
        Path to the saved ``.pkl`` file.
    """
    os.makedirs(SAVED_MODELS_DIR, exist_ok=True)
    filepath = os.path.join(SAVED_MODELS_DIR, f"{ticker}_{model_type}_h{horizon}_model.pkl")
    joblib.dump({"model": model, "scaler": scaler}, filepath)
    return filepath


def load_model(ticker: str, model_type: str = "random_forest", horizon: int = 1) -> tuple:
    """
    Load a previously saved model and scaler for *ticker*.

    Parameters
    ----------
    ticker : str
        Stock ticker symbol.
    model_type : str
        Model type used during training.
    horizon : int
        Forecast horizon used during training.

    Returns
    -------
    tuple[estimator, StandardScaler]
    """
    filepath = os.path.join(SAVED_MODELS_DIR, f"{ticker}_{model_type}_h{horizon}_model.pkl")
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"No saved model found at {filepath}. "
            "Run with --mode train first."
        )
    bundle = joblib.load(filepath)
    return bundle["model"], bundle["scaler"]


def save_metrics(metrics: dict, ticker: str, model_type: str, horizon: int) -> str:
    """
    Save training metrics and model metadata to a JSON file.

    The file is written to ``models/saved_models/{ticker}_{model_type}_h{horizon}_metrics.json``
    and contains holdout metrics, cross-validation metrics, and metadata
    such as the model type and forecast horizon.

    Returns
    -------
    str
        Path to the saved JSON file.
    """
    os.makedirs(SAVED_MODELS_DIR, exist_ok=True)
    filepath = os.path.join(SAVED_MODELS_DIR, f"{ticker}_{model_type}_h{horizon}_metrics.json")
    payload = {
        "ticker": ticker,
        "model_type": model_type,
        "horizon": horizon,
        **metrics,
    }
    with open(filepath, "w") as fh:
        json.dump(payload, fh, indent=2)
    return filepath

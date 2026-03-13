"""
predictor.py – Load a trained model and generate a price prediction for the
most recent trading day's data.
"""

import pandas as pd
from src.data_fetcher import fetch_stock_data
from src.preprocessor import add_technical_indicators, prepare_features, FEATURE_COLS
from src.model import load_model


def predict_next_close(ticker: str) -> float:
    """
    Predict the next-day closing price for *ticker*.

    Fetches the latest 90 days of data (enough to compute all indicators),
    applies feature engineering, loads the saved model, and returns the
    predicted closing price for the next trading day.

    Parameters
    ----------
    ticker : str
        Stock ticker symbol, e.g. ``"AAPL"``.

    Returns
    -------
    float
        Predicted next-day closing price.
    """
    df = fetch_stock_data(ticker, period="90d")
    df = add_technical_indicators(df)

    feature_cols = [c for c in FEATURE_COLS if c in df.columns]

    # Drop rows where any feature is NaN, then take the last row
    latest = df[feature_cols].dropna().iloc[[-1]]

    model, scaler = load_model(ticker)
    latest_scaled = scaler.transform(latest)
    prediction = model.predict(latest_scaled)[0]
    return float(prediction)

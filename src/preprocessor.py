"""
preprocessor.py – Feature engineering for stock price prediction.

Generates technical indicators from raw OHLCV data and prepares the
feature matrix (X) and target vector (y) for model training.
"""

import os
import pandas as pd
import numpy as np

PROCESSED_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

FEATURE_COLS = [
    "Open", "High", "Low", "Close", "Volume",
    "SMA_20", "SMA_50", "EMA_20",
    "RSI_14", "MACD", "MACD_Signal",
    "BB_Upper", "BB_Lower",
    "Daily_Return", "Volatility_20",
    # Additional indicators
    "ATR_14", "OBV", "Stoch_K", "Stoch_D", "Williams_R", "CCI_20",
]


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add commonly used technical indicators to *df*.

    Indicators added
    ----------------
    - SMA_20, SMA_50  : Simple moving averages (20-day and 50-day)
    - EMA_20          : Exponential moving average (20-day)
    - RSI_14          : Relative Strength Index (14-day)
    - MACD, MACD_Signal: Moving Average Convergence Divergence
    - BB_Upper, BB_Lower: Bollinger Bands (20-day, 2 std)
    - Daily_Return    : Percentage daily return
    - Volatility_20   : 20-day rolling standard deviation of returns
    - ATR_14          : Average True Range (14-day) – measures volatility
    - OBV             : On-Balance Volume – trend confirmation via volume
    - Stoch_K, Stoch_D: Stochastic Oscillator (14-day %K, 3-day SMA %D)
    - Williams_R      : Williams %R (14-day) – overbought/oversold signal
    - CCI_20          : Commodity Channel Index (20-day)

    Parameters
    ----------
    df : pd.DataFrame
        Raw OHLCV DataFrame (must contain a ``Close`` column).

    Returns
    -------
    pd.DataFrame
        Copy of *df* with additional indicator columns.
    """
    data = df.copy()
    close = data["Close"]

    # Simple & exponential moving averages
    data["SMA_20"] = close.rolling(window=20).mean()
    data["SMA_50"] = close.rolling(window=50).mean()
    data["EMA_20"] = close.ewm(span=20, adjust=False).mean()

    # RSI (14-day) — Wilder's smoothing (EMA with alpha=1/14)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    data["RSI_14"] = 100 - (100 / (1 + rs))

    # MACD
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    data["MACD"] = ema_12 - ema_26
    data["MACD_Signal"] = data["MACD"].ewm(span=9, adjust=False).mean()

    # Bollinger Bands (20-day)
    rolling_mean = close.rolling(window=20).mean()
    rolling_std = close.rolling(window=20).std()
    data["BB_Upper"] = rolling_mean + 2 * rolling_std
    data["BB_Lower"] = rolling_mean - 2 * rolling_std

    # Daily return & volatility
    data["Daily_Return"] = close.pct_change()
    data["Volatility_20"] = data["Daily_Return"].rolling(window=20).std()

    # Average True Range (ATR-14)
    high = data["High"]
    low = data["Low"]
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    data["ATR_14"] = true_range.rolling(window=14).mean()

    # On-Balance Volume (OBV) — vectorized
    direction = np.sign(close.diff())
    data["OBV"] = (direction * data["Volume"]).fillna(0).cumsum()

    # Stochastic Oscillator (14-day %K, 3-day SMA %D)
    low_14 = low.rolling(window=14).min()
    high_14 = high.rolling(window=14).max()
    hl_range = high_14 - low_14
    data["Stoch_K"] = np.where(hl_range > 1e-10, 100 * (close - low_14) / hl_range, np.nan)
    data["Stoch_D"] = pd.Series(data["Stoch_K"], index=data.index).rolling(window=3).mean()

    # Williams %R (14-day)
    data["Williams_R"] = np.where(hl_range > 1e-10, -100 * (high_14 - close) / hl_range, np.nan)

    # Commodity Channel Index (20-day)
    typical_price = (high + low + close) / 3
    cci_mean = typical_price.rolling(window=20).mean()
    cci_std = typical_price.rolling(window=20).std()
    data["CCI_20"] = np.where(cci_std > 1e-10, (typical_price - cci_mean) / (0.015 * cci_std), np.nan)

    return data


def prepare_features(df: pd.DataFrame, target_col: str = "Close", horizon: int = 1) -> tuple:
    """
    Prepare the feature matrix X and target vector y.

    The target is the closing price shifted *horizon* trading days into the
    future so the model learns to predict tomorrow's (or further) close.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame that already contains technical indicator columns.
    target_col : str
        Column to predict. Defaults to ``"Close"``.
    horizon : int
        Number of days ahead to predict. Defaults to ``1``.

    Returns
    -------
    tuple[pd.DataFrame, pd.Series]
        ``(X, y)`` after dropping rows with NaN values.
    """
    data = df.copy()
    data["Target"] = data[target_col].shift(-horizon)

    feature_cols = [c for c in FEATURE_COLS if c in data.columns]

    data = data[feature_cols + ["Target"]].dropna()
    X = data[feature_cols]
    y = data["Target"]
    return X, y


def save_processed_data(X: pd.DataFrame, y: pd.Series, ticker: str) -> str:
    """
    Persist the processed feature matrix and target to ``data/processed/``.

    Returns
    -------
    str
        Path to the saved CSV file.
    """
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    combined = X.copy()
    combined["Target"] = y
    filepath = os.path.join(PROCESSED_DATA_DIR, f"{ticker}_processed.csv")
    combined.to_csv(filepath)
    return filepath

"""
data_fetcher.py – Download historical stock data using yfinance and persist it
to data/raw/ as a CSV file.
"""

import os
import yfinance as yf
import pandas as pd

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def fetch_stock_data(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """
    Download historical OHLCV data for *ticker* from Yahoo Finance.

    Parameters
    ----------
    ticker : str
        Stock ticker symbol, e.g. ``"AAPL"``.
    period : str
        Lookback period accepted by yfinance, e.g. ``"1y"``, ``"2y"``, ``"5y"``.
    interval : str
        Data interval: ``"1d"``, ``"1wk"``, ``"1mo"``.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: Open, High, Low, Close, Volume, Dividends,
        Stock Splits.
    """
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'. Check the symbol and try again.")
    return df


def save_raw_data(df: pd.DataFrame, ticker: str) -> str:
    """
    Save *df* to ``data/raw/<ticker>.csv``.

    Returns
    -------
    str
        Absolute path to the saved file.
    """
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    filepath = os.path.join(RAW_DATA_DIR, f"{ticker}.csv")
    df.to_csv(filepath)
    return filepath


def load_raw_data(ticker: str) -> pd.DataFrame:
    """
    Load previously saved raw data from ``data/raw/<ticker>.csv``.

    Returns
    -------
    pd.DataFrame
    """
    filepath = os.path.join(RAW_DATA_DIR, f"{ticker}.csv")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Raw data file not found: {filepath}")
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    return df

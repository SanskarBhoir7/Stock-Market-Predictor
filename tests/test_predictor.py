"""
test_predictor.py – Unit tests for the Stock Market Predictor modules.

Tests use synthetic data so no network connection is required.
"""

import numpy as np
import pandas as pd
import pytest

from src.preprocessor import add_technical_indicators, prepare_features
from src.model import train_model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 120) -> pd.DataFrame:
    """Return a simple synthetic OHLCV DataFrame with *n* rows."""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame(
        {
            "Open": close * 0.99,
            "High": close * 1.01,
            "Low": close * 0.98,
            "Close": close,
            "Volume": np.random.randint(1_000_000, 5_000_000, size=n).astype(float),
        },
        index=pd.date_range("2022-01-01", periods=n, freq="B"),
    )
    return df


# ---------------------------------------------------------------------------
# preprocessor tests
# ---------------------------------------------------------------------------

class TestAddTechnicalIndicators:
    def test_returns_dataframe(self):
        df = _make_ohlcv()
        result = add_technical_indicators(df)
        assert isinstance(result, pd.DataFrame)

    def test_original_not_mutated(self):
        df = _make_ohlcv()
        original_cols = list(df.columns)
        add_technical_indicators(df)
        assert list(df.columns) == original_cols

    def test_expected_columns_present(self):
        df = _make_ohlcv()
        result = add_technical_indicators(df)
        expected = [
            "SMA_20", "SMA_50", "EMA_20",
            "RSI_14", "MACD", "MACD_Signal",
            "BB_Upper", "BB_Lower",
            "Daily_Return", "Volatility_20",
        ]
        for col in expected:
            assert col in result.columns, f"Missing column: {col}"

    def test_rsi_bounds(self):
        df = _make_ohlcv()
        result = add_technical_indicators(df)
        rsi = result["RSI_14"].dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_bollinger_bands_ordering(self):
        df = _make_ohlcv()
        result = add_technical_indicators(df).dropna()
        assert (result["BB_Upper"] >= result["BB_Lower"]).all()


class TestPrepareFeatures:
    def test_returns_tuple(self):
        df = add_technical_indicators(_make_ohlcv())
        result = prepare_features(df)
        assert isinstance(result, tuple) and len(result) == 2

    def test_no_nans_in_output(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        assert not X.isnull().any().any()
        assert not y.isnull().any()

    def test_consistent_lengths(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        assert len(X) == len(y)

    def test_horizon_shifts_target(self):
        df = add_technical_indicators(_make_ohlcv())
        _, y1 = prepare_features(df, horizon=1)
        _, y2 = prepare_features(df, horizon=2)
        # With a larger horizon fewer rows survive (NaN-drop removes more)
        assert len(y2) <= len(y1)


# ---------------------------------------------------------------------------
# model tests
# ---------------------------------------------------------------------------

class TestTrainModel:
    def test_returns_expected_keys(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        _, _, metrics = train_model(X, y)
        assert set(metrics.keys()) == {"mae", "rmse", "r2"}

    def test_metrics_are_finite(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        _, _, metrics = train_model(X, y)
        for name, value in metrics.items():
            assert np.isfinite(value), f"Metric '{name}' is not finite: {value}"

    def test_mae_non_negative(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        _, _, metrics = train_model(X, y)
        assert metrics["mae"] >= 0
        assert metrics["rmse"] >= 0

    def test_model_predicts_correct_shape(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        model, scaler, _ = train_model(X, y)
        preds = model.predict(scaler.transform(X))
        assert preds.shape == (len(X),)

"""
test_predictor.py – Unit tests for the Stock Market Predictor modules.

Tests use synthetic data so no network connection is required.
"""

import json
import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from src.preprocessor import add_technical_indicators, prepare_features
from src.model import (
    train_model,
    build_model,
    walk_forward_validation,
    save_model,
    load_model,
    save_metrics,
    SUPPORTED_MODELS,
)
from src.reporter import load_all_metrics, print_comparison_report


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


# ---------------------------------------------------------------------------
# New technical indicators tests
# ---------------------------------------------------------------------------

class TestNewTechnicalIndicators:
    def test_new_indicator_columns_present(self):
        df = _make_ohlcv()
        result = add_technical_indicators(df)
        new_cols = ["ATR_14", "OBV", "Stoch_K", "Stoch_D", "Williams_R", "CCI_20"]
        for col in new_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_stoch_k_bounds(self):
        df = _make_ohlcv()
        result = add_technical_indicators(df)
        stoch = result["Stoch_K"].dropna()
        assert (stoch >= 0).all() and (stoch <= 100).all()

    def test_williams_r_bounds(self):
        df = _make_ohlcv()
        result = add_technical_indicators(df)
        wr = result["Williams_R"].dropna()
        assert (wr >= -100).all() and (wr <= 0).all()

    def test_atr_non_negative(self):
        df = _make_ohlcv()
        result = add_technical_indicators(df)
        atr = result["ATR_14"].dropna()
        assert (atr >= 0).all()


# ---------------------------------------------------------------------------
# build_model tests
# ---------------------------------------------------------------------------

class TestBuildModel:
    def test_supported_model_types(self):
        for model_type in SUPPORTED_MODELS:
            model = build_model(model_type)
            assert model is not None

    def test_unsupported_model_raises(self):
        with pytest.raises(ValueError, match="Unknown model type"):
            build_model("invalid_model_type")


# ---------------------------------------------------------------------------
# walk_forward_validation tests
# ---------------------------------------------------------------------------

class TestWalkForwardValidation:
    def test_returns_expected_keys(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        cv = walk_forward_validation(X, y, model_type="random_forest", n_splits=3)
        expected = {"cv_mae_mean", "cv_mae_std", "cv_rmse_mean", "cv_rmse_std", "cv_r2_mean", "cv_r2_std"}
        assert expected == set(cv.keys())

    def test_cv_metrics_finite(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        cv = walk_forward_validation(X, y, model_type="linear_regression", n_splits=3)
        for key, val in cv.items():
            assert np.isfinite(val), f"CV metric '{key}' is not finite"

    def test_cv_mae_non_negative(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        cv = walk_forward_validation(X, y, n_splits=3)
        assert cv["cv_mae_mean"] >= 0
        assert cv["cv_mae_std"] >= 0


# ---------------------------------------------------------------------------
# multi-model train_model tests
# ---------------------------------------------------------------------------

class TestMultiModelTrain:
    @pytest.mark.parametrize("model_type", SUPPORTED_MODELS)
    def test_train_all_model_types(self, model_type):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        model, scaler, metrics = train_model(X, y, model_type=model_type)
        assert set(metrics.keys()) == {"mae", "rmse", "r2"}
        assert metrics["mae"] >= 0

    def test_xgboost_predicts_correct_shape(self):
        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        model, scaler, _ = train_model(X, y, model_type="xgboost")
        preds = model.predict(scaler.transform(X))
        assert preds.shape == (len(X),)


# ---------------------------------------------------------------------------
# save/load model tests
# ---------------------------------------------------------------------------

class TestSaveLoadModel:
    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        import src.model as model_module
        monkeypatch.setattr(model_module, "SAVED_MODELS_DIR", str(tmp_path))

        df = add_technical_indicators(_make_ohlcv())
        X, y = prepare_features(df)
        model, scaler, _ = train_model(X, y, model_type="linear_regression")

        save_model(model, scaler, "TEST", model_type="linear_regression", horizon=1)

        loaded_model, loaded_scaler = load_model("TEST", model_type="linear_regression", horizon=1)
        preds = loaded_model.predict(loaded_scaler.transform(X))
        assert preds.shape == (len(X),)

    def test_load_missing_model_raises(self, tmp_path, monkeypatch):
        import src.model as model_module
        monkeypatch.setattr(model_module, "SAVED_MODELS_DIR", str(tmp_path))

        with pytest.raises(FileNotFoundError):
            load_model("MISSING", model_type="random_forest", horizon=1)


# ---------------------------------------------------------------------------
# save_metrics & reporter tests
# ---------------------------------------------------------------------------

class TestSaveMetrics:
    def test_save_metrics_creates_json(self, tmp_path, monkeypatch):
        import src.model as model_module
        monkeypatch.setattr(model_module, "SAVED_MODELS_DIR", str(tmp_path))

        metrics = {"mae": 1.0, "rmse": 1.5, "r2": 0.9,
                   "cv_mae_mean": 1.1, "cv_mae_std": 0.1,
                   "cv_rmse_mean": 1.6, "cv_rmse_std": 0.1,
                   "cv_r2_mean": 0.88, "cv_r2_std": 0.02}
        path = save_metrics(metrics, "TEST", "random_forest", 1)
        assert os.path.exists(path)

        with open(path) as fh:
            data = json.load(fh)
        assert data["ticker"] == "TEST"
        assert data["model_type"] == "random_forest"
        assert data["horizon"] == 1
        assert data["mae"] == 1.0


class TestReporter:
    def test_load_all_metrics(self, tmp_path, monkeypatch):
        import src.model as model_module
        import src.reporter as reporter_module
        monkeypatch.setattr(model_module, "SAVED_MODELS_DIR", str(tmp_path))
        monkeypatch.setattr(reporter_module, "SAVED_MODELS_DIR", str(tmp_path))

        for mtype in ["random_forest", "xgboost"]:
            payload = {"ticker": "AAPL", "model_type": mtype, "horizon": 1,
                       "mae": 1.0, "rmse": 1.5, "r2": 0.9,
                       "cv_mae_mean": 1.1, "cv_mae_std": 0.1,
                       "cv_rmse_mean": 1.6, "cv_rmse_std": 0.1,
                       "cv_r2_mean": 0.88, "cv_r2_std": 0.02}
            filepath = tmp_path / f"AAPL_{mtype}_h1_metrics.json"
            filepath.write_text(json.dumps(payload))

        results = load_all_metrics("AAPL")
        assert len(results) == 2

    def test_print_report_no_metrics(self, tmp_path, monkeypatch, capsys):
        import src.reporter as reporter_module
        monkeypatch.setattr(reporter_module, "SAVED_MODELS_DIR", str(tmp_path))

        print_comparison_report("AAPL")
        captured = capsys.readouterr()
        assert "No metrics found" in captured.out

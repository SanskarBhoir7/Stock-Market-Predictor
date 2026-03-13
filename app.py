"""
app.py – Command-line entry point for the Stock Market Predictor.

Usage
-----
Train a model::

    python app.py --ticker AAPL --period 2y --mode train

Predict next close::

    python app.py --ticker AAPL --mode predict
"""

import argparse

from src.data_fetcher import fetch_stock_data, save_raw_data
from src.preprocessor import add_technical_indicators, prepare_features, save_processed_data
from src.model import train_model, save_model
from src.predictor import predict_next_close


def run_train(ticker: str, period: str) -> None:
    print(f"[INFO] Fetching {period} of data for {ticker} ...")
    df = fetch_stock_data(ticker, period=period)
    save_raw_data(df, ticker)
    print(f"[INFO] Raw data saved ({len(df)} rows).")

    print("[INFO] Engineering features ...")
    df = add_technical_indicators(df)
    X, y = prepare_features(df)
    save_processed_data(X, y, ticker)
    print(f"[INFO] Processed data saved ({len(X)} rows, {X.shape[1]} features).")

    print("[INFO] Training model ...")
    model, scaler, metrics = train_model(X, y)
    model_path = save_model(model, scaler, ticker)
    print(f"[INFO] Model saved to {model_path}")
    print(
        f"[METRICS] MAE={metrics['mae']:.4f}  "
        f"RMSE={metrics['rmse']:.4f}  "
        f"R²={metrics['r2']:.4f}"
    )


def run_predict(ticker: str) -> None:
    print(f"[INFO] Predicting next close for {ticker} ...")
    prediction = predict_next_close(ticker)
    print(f"[RESULT] Predicted next closing price for {ticker}: ${prediction:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock Market Predictor")
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol (e.g. AAPL)")
    parser.add_argument(
        "--period",
        default="2y",
        help="Historical data period for training (e.g. 1y, 2y, 5y). Default: 2y",
    )
    parser.add_argument(
        "--mode",
        choices=["train", "predict"],
        required=True,
        help="'train' to train and save a model; 'predict' to load and predict",
    )
    args = parser.parse_args()

    if args.mode == "train":
        run_train(args.ticker, args.period)
    else:
        run_predict(args.ticker)


if __name__ == "__main__":
    main()

"""
app.py – Command-line entry point for the Stock Market Predictor.

Usage
-----
Train a model::

    python app.py --ticker AAPL --period 2y --mode train --model random_forest --horizon 1

Predict next close::

    python app.py --ticker AAPL --mode predict --model random_forest --horizon 1

Compare all trained models for a ticker::

    python app.py --ticker AAPL --mode compare
"""

import argparse

from src.data_fetcher import fetch_stock_data, save_raw_data
from src.preprocessor import add_technical_indicators, prepare_features, save_processed_data
from src.model import train_model, save_model, save_metrics, walk_forward_validation, SUPPORTED_MODELS
from src.predictor import predict_next_close
from src.reporter import print_comparison_report


def run_train(ticker: str, period: str, model_type: str, horizon: int) -> None:
    """Fetch data, engineer features, train the chosen model, and save everything."""
    print(f"[INFO] Fetching {period} of data for {ticker} ...")
    df = fetch_stock_data(ticker, period=period)
    save_raw_data(df, ticker)
    print(f"[INFO] Raw data saved ({len(df)} rows).")

    print("[INFO] Engineering features ...")
    df = add_technical_indicators(df)
    X, y = prepare_features(df, horizon=horizon)
    save_processed_data(X, y, ticker)
    print(f"[INFO] Processed data saved ({len(X)} rows, {X.shape[1]} features).")

    print(f"[INFO] Training {model_type} model (horizon={horizon} day(s)) ...")
    model, scaler, metrics = train_model(X, y, model_type=model_type)
    model_path = save_model(model, scaler, ticker, model_type=model_type, horizon=horizon)
    print(f"[INFO] Model saved to {model_path}")
    print(
        f"[METRICS] MAE={metrics['mae']:.4f}  "
        f"RMSE={metrics['rmse']:.4f}  "
        f"R²={metrics['r2']:.4f}"
    )

    print("[INFO] Running walk-forward cross-validation ...")
    cv_metrics = walk_forward_validation(X, y, model_type=model_type)
    print(
        f"[CV]     MAE={cv_metrics['cv_mae_mean']:.4f} ± {cv_metrics['cv_mae_std']:.4f}  "
        f"RMSE={cv_metrics['cv_rmse_mean']:.4f} ± {cv_metrics['cv_rmse_std']:.4f}  "
        f"R²={cv_metrics['cv_r2_mean']:.4f} ± {cv_metrics['cv_r2_std']:.4f}"
    )

    all_metrics = {**metrics, **cv_metrics}
    metrics_path = save_metrics(all_metrics, ticker, model_type=model_type, horizon=horizon)
    print(f"[INFO] Metrics saved to {metrics_path}")


def run_predict(ticker: str, model_type: str, horizon: int) -> None:
    """Load the saved model and predict the price *horizon* days ahead."""
    print(f"[INFO] Predicting {horizon}-day-ahead close for {ticker} using {model_type} ...")
    prediction = predict_next_close(ticker, model_type=model_type, horizon=horizon)
    print(
        f"[RESULT] Predicted closing price for {ticker} "
        f"({horizon} day(s) ahead): ${prediction:.2f}"
    )


def run_compare(ticker: str, horizon: int | None) -> None:
    """Print a comparison report of all trained models for *ticker*."""
    print_comparison_report(ticker, horizon=horizon)


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
        choices=["train", "predict", "compare"],
        required=True,
        help="'train' to train and save a model; 'predict' to load and predict; "
             "'compare' to show a performance report across trained models",
    )
    parser.add_argument(
        "--model",
        dest="model_type",
        choices=SUPPORTED_MODELS,
        default="random_forest",
        help="Model type to train or predict with. Default: random_forest",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        choices=[1, 3, 5],
        default=None,
        help="Forecast horizon in trading days (1, 3, or 5). Default: 1",
    )
    args = parser.parse_args()

    # Resolve horizon: default to 1 when not explicitly provided
    horizon = args.horizon if args.horizon is not None else 1

    if args.mode == "train":
        run_train(args.ticker, args.period, args.model_type, horizon)
    elif args.mode == "predict":
        run_predict(args.ticker, args.model_type, horizon)
    else:
        # In compare mode, show all horizons unless the user explicitly passed --horizon
        run_compare(args.ticker, horizon=args.horizon)


if __name__ == "__main__":
    main()

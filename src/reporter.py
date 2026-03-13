"""
reporter.py – Compare trained models and display a summary performance report.

Reads the JSON metrics files saved by :func:`src.model.save_metrics` and
prints a formatted table so the user can see which model performs best for
a given ticker and forecast horizon.
"""

import os
import json
import glob

from src.model import SAVED_MODELS_DIR, SUPPORTED_MODELS


def load_all_metrics(ticker: str) -> list[dict]:
    """
    Load all saved metrics JSON files for *ticker*.

    Looks for files matching ``{ticker}_*_h*_metrics.json`` inside
    ``models/saved_models/``.

    Returns
    -------
    list[dict]
        List of metric dicts, each containing at minimum ``model_type``,
        ``horizon``, ``mae``, ``rmse``, and ``r2``.
    """
    pattern = os.path.join(SAVED_MODELS_DIR, f"{ticker}_*_metrics.json")
    results = []
    for filepath in sorted(glob.glob(pattern)):
        with open(filepath) as fh:
            results.append(json.load(fh))
    return results


def print_comparison_report(ticker: str, horizon: int | None = None) -> None:
    """
    Print a comparison table of all trained models for *ticker*.

    Parameters
    ----------
    ticker : str
        Stock ticker symbol.
    horizon : int or None
        If given, only show models with this forecast horizon.
        If ``None``, show all horizons.
    """
    records = load_all_metrics(ticker)

    if not records:
        print(
            f"[WARN] No metrics found for ticker '{ticker}'. "
            "Train at least one model first with --mode train."
        )
        return

    if horizon is not None:
        records = [r for r in records if r.get("horizon") == horizon]

    if not records:
        print(f"[WARN] No metrics found for ticker '{ticker}' with horizon={horizon}.")
        return

    # Sort by MAE ascending (lower is better)
    records.sort(key=lambda r: r.get("mae", float("inf")))

    col_w = 18
    header = (
        f"{'Model':<{col_w}} {'Horizon':>7}  "
        f"{'MAE':>10}  {'RMSE':>10}  {'R²':>8}  "
        f"{'CV MAE (mean)':>14}  {'CV MAE (std)':>13}"
    )
    separator = "-" * len(header)

    print(f"\n{'=' * len(header)}")
    print(f"  Model Comparison Report – {ticker}")
    print(f"{'=' * len(header)}")
    print(header)
    print(separator)

    for i, rec in enumerate(records):
        model_label = rec.get("model_type", "unknown")
        if i == 0:
            model_label += " ★"  # mark best model
        print(
            f"{model_label:<{col_w}} {rec.get('horizon', '?'):>7}  "
            f"{rec.get('mae', float('nan')):>10.4f}  "
            f"{rec.get('rmse', float('nan')):>10.4f}  "
            f"{rec.get('r2', float('nan')):>8.4f}  "
            f"{rec.get('cv_mae_mean', float('nan')):>14.4f}  "
            f"{rec.get('cv_mae_std', float('nan')):>13.4f}"
        )

    print(separator)
    best = records[0]
    print(
        f"\n[BEST] {best.get('model_type')} "
        f"(horizon={best.get('horizon')}) "
        f"→ MAE={best.get('mae', float('nan')):.4f}\n"
    )

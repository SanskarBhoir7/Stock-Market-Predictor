# Stock-Market-Predictor

A command-line machine learning project that predicts future stock closing prices from historical market data and technical indicators.

## Features

- Download historical stock data with `yfinance`
- Engineer technical indicators such as `SMA`, `EMA`, `RSI`, `MACD`, Bollinger Bands, `ATR`, `OBV`, stochastic oscillator, `Williams %R`, and `CCI`
- Train multiple regression models:
  - `random_forest`
  - `xgboost`
  - `linear_regression`
- Predict prices `1`, `3`, or `5` trading days ahead
- Evaluate models with holdout metrics: `MAE`, `RMSE`, and `R2`
- Run walk-forward time-series cross-validation
- Save trained models, scalers, and metrics locally
- Compare trained models for a ticker using a CLI report

## Project Structure

```text
Stock-Market-Predictor/
|-- app.py
|-- requirements.txt
|-- data/
|   |-- raw/
|   `-- processed/
|-- models/
|   `-- saved_models/
|-- notebooks/
|   `-- exploratory_analysis.ipynb
|-- src/
|   |-- __init__.py
|   |-- data_fetcher.py
|   |-- preprocessor.py
|   |-- model.py
|   |-- predictor.py
|   `-- reporter.py
`-- tests/
    |-- __init__.py
    `-- test_predictor.py
```

## Setup

```bash
# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## CLI Modes

The application supports three modes:

- `train`: fetch data, engineer features, train a model, evaluate it, and save artifacts
- `predict`: load a previously trained model and predict a future closing price
- `compare`: show a report of saved model metrics for a ticker

## Usage

### Train a model

```bash
python app.py --ticker AAPL --period 2y --mode train --model random_forest --horizon 1
python app.py --ticker AAPL --period 2y --mode train --model xgboost --horizon 3
python app.py --ticker AAPL --period 5y --mode train --model linear_regression --horizon 5
```

### Predict with a saved model

```bash
python app.py --ticker AAPL --mode predict --model random_forest --horizon 1
python app.py --ticker AAPL --mode predict --model xgboost --horizon 3
```

### Compare trained models

```bash
python app.py --ticker AAPL --mode compare
python app.py --ticker AAPL --mode compare --horizon 3
```

## Command Arguments

- `--ticker`: stock ticker symbol, for example `AAPL`
- `--period`: training history to download, for example `1y`, `2y`, or `5y`
- `--mode`: one of `train`, `predict`, or `compare`
- `--model`: one of `random_forest`, `xgboost`, or `linear_regression`
- `--horizon`: forecast horizon in trading days, one of `1`, `3`, or `5`

## Saved Outputs

Training creates artifacts inside `models/saved_models/`:

- model bundle: `<ticker>_<model>_h<horizon>_model.pkl`
- metrics file: `<ticker>_<model>_h<horizon>_metrics.json`

Raw and processed datasets are saved in:

- `data/raw/`
- `data/processed/`

## Example Workflow

```bash
# Train several models
python app.py --ticker AAPL --period 2y --mode train --model random_forest --horizon 1
python app.py --ticker AAPL --period 2y --mode train --model xgboost --horizon 1
python app.py --ticker AAPL --period 2y --mode train --model linear_regression --horizon 1

# Compare their saved metrics
python app.py --ticker AAPL --mode compare --horizon 1

# Use the best one for prediction
python app.py --ticker AAPL --mode predict --model xgboost --horizon 1
```

## Running Tests

```bash
python -m pytest tests/
```

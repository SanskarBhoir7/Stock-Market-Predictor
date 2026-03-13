# Stock-Market-Predictor

A machine learning application that predicts stock market prices using historical data and technical indicators.

## Features

- Fetch historical stock data via `yfinance`
- Preprocess data and engineer technical indicators (moving averages, RSI, MACD, etc.)
- Train a machine learning model (Random Forest) to predict future closing prices
- Evaluate model performance and visualise predictions

## Project Structure

```
Stock-Market-Predictor/
├── app.py                  # Main entry point
├── requirements.txt        # Python dependencies
├── data/
│   ├── raw/                # Raw downloaded stock data
│   └── processed/          # Preprocessed feature data
├── models/
│   └── saved_models/       # Persisted trained models
├── notebooks/
│   └── exploratory_analysis.ipynb  # EDA notebook
├── src/
│   ├── __init__.py
│   ├── data_fetcher.py     # Download stock data
│   ├── preprocessor.py     # Feature engineering
│   ├── model.py            # Model training and evaluation
│   └── predictor.py        # Load model and make predictions
└── tests/
    ├── __init__.py
    └── test_predictor.py   # Unit tests
```

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
# Train a model for a given ticker (e.g. AAPL) over the last 2 years
python app.py --ticker AAPL --period 2y --mode train

# Predict the next closing price using a saved model
python app.py --ticker AAPL --mode predict
```

## Running Tests

```bash
python -m pytest tests/
```

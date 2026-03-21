# AI Trading Engine

AI Trading Engine is a full-stack market intelligence MVP for Indian equities. It combines authentication, market data, charting, advanced NLP sentiment analysis, and a concurrent multi-agent prediction pipeline into one comprehensive dashboard.

## What This Repo Contains

- `frontend/`: React + Vite dashboard UI with `vitest` unit tests
- `backend/`: FastAPI API with auth, rate-limiting, Alembic migrations, async market-analysis endpoints, and `pytest` integration tests
- `models/`, `data/`, `notebooks/`, `src/`: Core ML pipeline for training offline models and performing data analysis

## Features

- **Secure JWT Auth**: Features password strength validation, IP-based login rate limiting, and 1-hour token expiries.
- **Market Data**: Ticker search suggestions, market snapshots, and historical OHLC data for candlestick charts.
- **NLP Sentiment**: Integration with `vaderSentiment` for robust, finance-aware lexical scoring of news headlines.
- **Async Multi-Agent Analysis**: A concurrent, `asyncio`-driven multi-agent pipeline spanning macro, technical, fundamental, commodities, and sentiment analysis.
- **ML Pipeline**: A locally trained Random Forest/XGBoost prediction pipeline accessible via the `/ml-prediction` endpoint.
- **Database Support**: Alembic schema migrations for SQLite (local fallback) and MySQL databases.

## Tech Stack

- **Frontend**: React, Vite, Tailwind CSS, Axios, lightweight-charts, Vitest
- **Backend**: FastAPI, SQLAlchemy, Alembic, Pydantic, yfinance, PyMySQL, python-jose, cachetools, HTTPX, Pytest
- **AI/ML**: pandas, scikit-learn, xgboost, vaderSentiment

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Node.js 18+
- Optional: MySQL on `localhost:3306` (for persistent DB instead of SQLite fallback)

### 2. Backend Setup

```bash
# Set up the environment
python -m venv venv
venv\Scripts\activate  # On Windows

# Install all dependencies
pip install -r requirements.txt

cd backend
cp .env.example .env

# Initialize Database Migrations
alembic upgrade head

# Run the Server
uvicorn main:app --reload --port 8000
```

Notes:
- If `DATABASE_URL` is set, the backend uses it.
- Else if `MYSQL_PASSWORD` is non-empty, the backend builds a MySQL URL from `MYSQL_*`.
- Else backend falls back to SQLite at `backend/ai_trading.db`.
- If `UPSTOX_ACCESS_TOKEN` is blank, the app runs in `yfinance-only` mode.

### 3. Frontend Setup

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Default frontend env:
```env
VITE_API_URL=http://localhost:8000/api/v1
```

### 4. Run Tests

- **Backend Integration Tests**: Execute `pytest backend/tests/test_api.py -v` from the project root.
- **Frontend Component Tests**: Execute `npx vitest` from the `frontend/` directory.

### 5. Application URLs

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Backend Environment Variables

`backend/.env.example` is the source of truth. Important keys:

- `APP_ENV`
- `DATABASE_URL`
- `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_SERVER`, `MYSQL_PORT`, `MYSQL_DB`
- `SQLITE_DB_PATH`
- `SECRET_KEY` *(Must be changed from default in production)*
- `FRONTEND_ORIGINS`
- `UPSTOX_ACCESS_TOKEN`, `UPSTOX_BASE_URL`
- `TWELVE_DATA_API_KEY`, `TWELVE_DATA_BASE_URL`

## API Routes (v1)

Base prefix: `/api/v1`

**Auth:**
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

**Market:**
- `GET /market/search-suggestions?q=RELIANCE&limit=8`
- `GET /market/data?ticker=RELIANCE.NS`
- `GET /market/historical?ticker=RELIANCE.NS&period=6mo`
- `GET /market/news?ticker=RELIANCE.NS`
- `GET /market/prediction?ticker=RELIANCE.NS&horizon=1d`
- `GET /market/realtime-analysis?ticker=RELIANCE.NS&horizon=1d`
- `GET /market/ml-prediction?ticker=RELIANCE.NS&model_type=random_forest&horizon=1`

**Health:**
- `GET /`
- `GET /health`

*Note: Most market routes require a valid bearer JWT token from `/api/v1/auth/login`.*

## Current Status

Following recent security hardening, architectural refactoring, and AI enhancements:
- The application effectively prevents mass-credential/brute-force attacks via rate limiters and strict password strength validation.
- Agent latency has been significantly optimized by leveraging asynchronous parallelization.
- The repository includes tests and database migration infrastructure, making it significantly more robust for real-world deployments.

# AI Trading Engine

AI Trading Engine is a full-stack market intelligence MVP for Indian equities. It combines authentication, market data, charting, news sentiment, and a multi-agent prediction pipeline into one dashboard.

## What This Repo Contains

- `frontend/`: React + Vite dashboard UI
- `backend/`: FastAPI API with auth and market-analysis endpoints
- `models/`, `data/`, `notebooks/`, `src/`, `tests/`: research and project assets from earlier development stages

## Features

- JWT auth (`register`, `login`, `me`)
- Ticker search suggestions
- Market snapshot endpoint (with fallback logic)
- Historical OHLC endpoint for candlestick charts
- Headline sentiment tagging
- Multi-agent prediction and realtime analysis endpoints
- SQLite fallback for local demo mode when MySQL credentials are not set

## Tech Stack

- Frontend: React, Vite, Tailwind CSS, Axios, lightweight-charts
- Backend: FastAPI, SQLAlchemy, Pydantic, yfinance, PyMySQL, python-jose

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Node.js 18+
- Optional: MySQL on `localhost:3306` (for persistent DB instead of SQLite fallback)

### 2. Backend Setup

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Notes:

- If `DATABASE_URL` is set, backend uses it.
- Else if `MYSQL_PASSWORD` is non-empty, backend builds a MySQL URL from `MYSQL_*`.
- Else backend falls back to SQLite at `backend/ai_trading.db`.

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

### 4. Run the App

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Backend Environment Variables

`backend/.env.example` is the source of truth. Important keys:

- `APP_ENV`
- `DATABASE_URL`
- `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_SERVER`, `MYSQL_PORT`, `MYSQL_DB`
- `SQLITE_DB_PATH`
- `SECRET_KEY`
- `FRONTEND_ORIGINS`
- `UPSTOX_ACCESS_TOKEN`, `UPSTOX_BASE_URL`
- `TWELVE_DATA_API_KEY`, `TWELVE_DATA_BASE_URL`
- `LLM_API_KEY`

## API Routes (v1)

Base prefix: `/api/v1`

Auth:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

Market:

- `GET /market/search-suggestions?q=RELIANCE&limit=8`
- `GET /market/data?ticker=RELIANCE.NS`
- `GET /market/historical?ticker=RELIANCE.NS&period=6mo`
- `GET /market/news?ticker=RELIANCE.NS`
- `GET /market/prediction?ticker=RELIANCE.NS&horizon=1d`
- `GET /market/realtime-analysis?ticker=RELIANCE.NS&horizon=1d`

Health:

- `GET /`
- `GET /health`

Most market routes require a valid bearer token from `/auth/login`.

## Current Status

This is a working MVP and is suitable for demo and iteration, not production deployment yet.

Known limitations:

- Prediction/sentiment logic is heuristic and not fully validated
- Security/deployment hardening is still needed
- Test coverage is limited and should be expanded

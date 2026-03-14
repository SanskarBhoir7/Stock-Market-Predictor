# AI Trading Engine

AI Trading Engine is a full-stack market intelligence platform for Indian equities. It combines live market data, charting, headline sentiment, and a multi-agent analysis pipeline into a single dashboard for faster decision support.

This repo is currently best described as a **working MVP**: the product surface is real, the frontend is buildable, and the backend has live analysis routes, but it is not yet a final research-grade or deployment-ready system.

## Overview

Retail investors often work with fragmented information. Price action, recent headlines, broader market signals, and basic risk context usually live across multiple tools. AI Trading Engine brings those inputs into one interface so users can inspect a stock, review recent sentiment, and understand the model's directional outlook more quickly.

The current MVP includes:

- React dashboard with authentication
- FastAPI backend with market and auth routes
- Multi-agent scoring pipeline using live Yahoo Finance data
- Search, chart, news, and prediction flow wired end-to-end

## Key Features

- **Multi-agent backend pipeline:** FastAPI backend orchestrates macro, commodities/FX, news, technical, and risk layers.
- **Real-time market data:** Pulls live OHLCV data, fundamentals, and ticker search results through `yfinance`.
- **Signal-fusion prediction:** Produces a directional call, confidence score, probability split, and projected range.
- **News sentiment layer:** Reviews recent ticker headlines and assigns lightweight sentiment tags.
- **Interactive charting:** Uses `lightweight-charts` for candlestick visualization.
- **JWT authentication:** Supports user registration, login, and protected market routes.
- **Responsive dashboard UI:** Built with React and Tailwind for a polished live-demo experience.

## Architecture

The backend exposes a live **multi-agent market analysis** pipeline.

Currently wired agents:

- **`MacroGeopoliticsAgent`**: Tracks global index breadth, VIX pressure, and geopolitical keyword risk.
- **`CommoditiesFxAgent`**: Monitors crude, metals, USDINR, DXY, and US10Y impact on equity risk.
- **`NewsSentimentAgent`**: Scores ticker headlines with lexical sentiment and severe-event penalties.
- **`TechnicalFlowAgent`**: Computes trend regime, RSI context, breakout confirmation, and volume spikes.
- **`RiskManagerAgent`**: Fuses agent signals into the final call, confidence, probability split, and risk plan.

Main prediction routes:

- `GET /api/v1/market/prediction?ticker=RELIANCE.NS&horizon=1d`
- `GET /api/v1/market/realtime-analysis?ticker=RELIANCE.NS&horizon=1d`

## Technology Stack

**Frontend**

- React (Vite)
- Tailwind CSS
- TradingView Lightweight Charts
- Axios
- React Router
- Lucide React

**Backend**

- FastAPI
- Python 3.10+
- SQLAlchemy
- MySQL
- PyMySQL
- JWT via `python-jose`
- Password hashing
- `yfinance`
- Pandas and NumPy

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ and `npm`
- MySQL running locally on port `3306`

### 1. Create the database

Create a local MySQL database named `ai_trading`.

```sql
CREATE DATABASE ai_trading;
```

### 2. Configure the backend

Create `backend/.env` from `backend/.env.example` and set your secrets before running the backend.

If you do not provide MySQL credentials, the backend falls back to a local SQLite database for easier demos.

Install backend dependencies and start the server:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Open the app

1. Visit `http://localhost:5173`
2. Create an account
3. Log in
4. Search tickers such as `RELIANCE.NS`, `TCS.NS`, or `HDFCBANK.NS`

## Roadmap

The fastest improvements that would make this repo much stronger are:

1. Expand backend and frontend automated test coverage.
2. Add reproducible backend tests for auth and market routes.
3. Add a metrics section showing historical validation or model performance.
4. Reframe the product around a sharper user-impact story.
5. Add production-ready integrations such as cloud deployment, analytics, or LLM-backed explanations.

## Current Status

What is already strong:

- End-to-end product structure
- Live market and analysis experience
- Clean frontend demo surface
- Distinct multi-agent design instead of a single black-box score

What is still risky:

- Demo startup is easiest with the new SQLite fallback, but production still needs stronger DB setup
- Current sentiment and prediction logic is heuristic, not deeply validated
- README claims should stay aligned with what the code really does
- Security and deployment hardening are still needed

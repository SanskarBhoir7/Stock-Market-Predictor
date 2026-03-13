# AI Trading Engine

A full-stack algorithmic trading platform designed for the Indian equity market (NSE/BSE). This application integrates real-time financial tracking, sentiment analysis through natural language processing (NLP), and advanced machine learning predictive models (TimeGAN / WGAN-GP) into a highly responsive, glassmorphic React dashboard.

## 🌟 Key Features

- **Multi-Agent Backend Architecture:** Powered by a fast and scalable FastAPI server.
- **Real-time Indian Market Data:** Integrates directly with `yfinance` to scrape live OHLCV data, fundamentals, and financials (append `.NS` or `.BO` to tickers).
- **AI TimeGAN Forecaster:** Generates intelligent upper and lower prediction bounds analyzing historical price volatility and directional NLP sentiment bias.
- **Sentiment Analyzer Agent:** Ingests live Yahoo Finance headlines and flags them automatically as `POSITIVE`, `NEGATIVE`, or `NEUTRAL`.
- **Professional Grade Charting:** Implements native local `lightweight-charts` by TradingView to render hyper-fluid Candlestick graphics.
- **Secure JWT Authentication:** Implements `bcrypt` password hashing and secure JSON Web Tokens stored via a strict React `AuthContext` pipeline.
- **Beautiful UI/UX:** Built on Vite + React + Tailwind CSS utilizing dynamic colors, glassmorphism overlays, and smooth CSS transitions.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js (v18+)** and `npm`
- **MySQL Server** (Running locally on default port `3306`)

### 1. Database Configuration (MySQL)

Create a local MySQL database named `ai_trading` and ensure your root configuration matches the `backend/core/config.py` definitions.

```sql
CREATE DATABASE ai_trading;
```

### 2. Backend Setup (FastAPI)

Navigate to the `backend` directory, initialize the Python virtual environment, and install dependencies:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install all AI and System dependencies
pip install fastapi uvicorn sqlalchemy pymysql pydantic pydantic-settings python-dotenv python-jose[cryptography] bcrypt langchain openai scikit-learn numpy pandas yfinance "pydantic[email]" python-multipart tensorflow keras

# Boot the FastAPI Server
uvicorn main:app --reload --port 8000
```

The database tables (like `users`) will automatically be created on the very first boot.

### 3. Frontend Setup (React/Vite)

Open a new terminal window, navigate to the `frontend` directory:

```bash
cd frontend

# Install Node modules
npm install
npm install lightweight-charts lucide-react axios react-router-dom

# Start the Development Server
npm run dev
```

### 4. Accessing the Platform

1. Open your browser and navigate to `http://localhost:5173`.
2. As the database starts empty, click **Sign up** at the bottom of the card to create your first account.
3. Upon registration, you will be redirected to the Dashboard.
4. Try searching Indian tickers like `RELIANCE.NS`, `TCS.NS`, or `HDFCBANK.NS`.

---

## 🛠️ Technology Stack

**Frontend:**

- React (Vite)
- Tailwind CSS (Dark Mode, Glassmorphic UI)
- TradingView Lightweight Charts
- Axios (HTTP Interceptors for Auth)
- React Router DOM
- Lucide React Icons

**Backend:**

- FastAPI
- Python 3.10+
- MySQL (SQLAlchemy ORM)
- PyMySQL Driver
- JWT (python-jose)
- bcrypt Password Hashing
- TensorFlow / Keras (For Agent Models)
- yfinance (Data Parsing)
- Pandas & Numpy

---

## 🛡️ Architecture & Agents

The backend now runs a live **Multi-Agent System** orchestration pipeline.
Currently wired agents:

- **`MacroGeopoliticsAgent`**: Tracks global index breadth, VIX pressure, and geopolitical keyword risk.
- **`CommoditiesFxAgent`**: Monitors crude, metals, USDINR, DXY, and US10Y impact on equity risk.
- **`NewsSentimentAgent`**: Scores ticker news with severe-event penalties and headline relevance.
- **`TechnicalFlowAgent`**: Computes trend regime, RSI context, breakout confirmation, and volume spikes.
- **`RiskManagerAgent`**: Performs weighted fusion and returns final call, confidence, bounds, and risk plan.

Main prediction routes:
- `GET /api/v1/market/prediction?ticker=RELIANCE.NS&horizon=1d`
- `GET /api/v1/market/realtime-analysis?ticker=RELIANCE.NS&horizon=1d`

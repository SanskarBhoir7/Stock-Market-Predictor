from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
import yfinance as yf

from agents.coordinator_agent import CoordinatorAgent
from api import deps
from core.demo_data import get_demo_bundle, has_demo_data, supported_demo_tickers

router = APIRouter()
coordinator = CoordinatorAgent()
_CACHE_TTL_SECONDS = 60
_memory_cache: Dict[str, Dict[str, Any]] = {}

DEMO_TICKER_METADATA: Dict[str, Dict[str, str]] = {
    "RELIANCE.NS": {
        "company_name": "Reliance Industries Ltd",
        "sector": "Energy / Conglomerate",
    },
    "TCS.NS": {
        "company_name": "Tata Consultancy Services Ltd",
        "sector": "Information Technology",
    },
    "HDFCBANK.NS": {
        "company_name": "HDFC Bank Ltd",
        "sector": "Banking",
    },
}


def _safe_info(stock: yf.Ticker) -> Dict[str, Any]:
    try:
        return stock.info or {}
    except Exception:
        return {}


def _safe_fast_info(stock: yf.Ticker) -> Dict[str, Any]:
    try:
        fast_info = stock.fast_info
        if hasattr(fast_info, "items"):
            return dict(fast_info.items())
    except Exception:
        pass
    return {}


def _safe_history(stock: yf.Ticker, period: str):
    try:
        return stock.history(period=period)
    except Exception:
        return None


def _format_market_cap(value: Any) -> str:
    if value in (None, "", "N/A"):
        return "N/A"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if numeric >= 1_000_000_000_000:
        return f"Rs {numeric / 1_000_000_000_000:.2f}T"
    if numeric >= 1_000_000_000:
        return f"Rs {numeric / 1_000_000_000:.2f}B"
    if numeric >= 1_000_000:
        return f"Rs {numeric / 1_000_000:.2f}M"
    return f"Rs {numeric:.0f}"


def _resolve_profile(ticker: str, info: Dict[str, Any]) -> Dict[str, str]:
    profile = DEMO_TICKER_METADATA.get(ticker.upper(), {})
    return {
        "company_name": info.get("shortName") or info.get("longName") or profile.get("company_name") or ticker,
        "sector": info.get("sector") or profile.get("sector") or "Unknown",
    }


def _close_values(hist) -> List[float]:
    if hist is None or hist.empty or "Close" not in hist:
        return []
    return [float(v) for v in hist["Close"].dropna().tolist()]


def _is_market_closed_context() -> bool:
    # Treat weekends as expected non-live periods for demo messaging.
    return datetime.now().weekday() >= 5


def _cache_get(key: str):
    cached = _memory_cache.get(key)
    if not cached:
        return None
    if cached["expires_at"] < datetime.utcnow():
        _memory_cache.pop(key, None)
        return None
    return cached["value"]


def _cache_set(key: str, value: Any, ttl_seconds: int = _CACHE_TTL_SECONDS) -> Any:
    _memory_cache[key] = {
        "value": value,
        "expires_at": datetime.utcnow() + timedelta(seconds=ttl_seconds),
    }
    return value


@router.get("/search-suggestions", response_model=List[Dict[str, str]])
def get_search_suggestions(
    q: str,
    limit: int = 8,
    current_user=Depends(deps.get_current_user),
) -> Any:
    """
    Return ticker autocomplete suggestions from Yahoo Finance search.
    """
    try:
        query = (q or "").strip()
        if len(query) < 2:
            return []
        if "." in query and len(query) >= 6:
            return []

        cache_key = f"search::{query.lower()}::{limit}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        safe_limit = max(1, min(int(limit), 15))
        search = yf.Search(query=query, max_results=safe_limit)
        quotes = getattr(search, "quotes", []) or []

        suggestions: List[Dict[str, str]] = []
        seen = set()
        for item in quotes:
            symbol = (item.get("symbol") or "").strip().upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            suggestions.append(
                {
                    "symbol": symbol,
                    "name": (item.get("shortname") or item.get("longname") or symbol).strip(),
                    "exchange": (item.get("exchange") or item.get("exchDisp") or "").strip(),
                    "type": (item.get("quoteType") or "").strip(),
                }
            )
            if len(suggestions) >= safe_limit:
                break

        return _cache_set(cache_key, suggestions, ttl_seconds=120)
    except Exception:
        lowered_query = query.lower()
        fallback = []
        for symbol in supported_demo_tickers():
            if lowered_query in symbol.lower():
                bundle = get_demo_bundle(symbol)
                fallback.append(
                    {
                        "symbol": symbol,
                        "name": bundle["data"]["company_name"],
                        "exchange": "NSE",
                        "type": "EQUITY",
                    }
                )
        return fallback[:limit]


@router.get("/data", response_model=Dict[str, Any])
def get_market_data(ticker: str, current_user=Depends(deps.get_current_user)) -> Any:
    """
    Fetch market data with layered fallbacks:
    info -> fast_info -> historical prices -> local metadata.
    """
    try:
        cache_key = f"data::{ticker.upper()}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        stock = yf.Ticker(ticker)
        info = _safe_info(stock)
        fast_info = _safe_fast_info(stock)
        hist_5d = _safe_history(stock, "5d")
        hist_1y = _safe_history(stock, "1y")

        closes_5d = _close_values(hist_5d)
        closes_1y = _close_values(hist_1y)
        has_hist_1y = hist_1y is not None and not hist_1y.empty

        profile = _resolve_profile(ticker, info)

        current_price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or fast_info.get("lastPrice")
            or (closes_5d[-1] if closes_5d else None)
            or (closes_1y[-1] if closes_1y else None)
        )
        previous_close = (
            info.get("previousClose")
            or fast_info.get("previousClose")
            or (closes_5d[-2] if len(closes_5d) >= 2 else None)
            or current_price
        )

        if current_price is None:
            if has_demo_data(ticker):
                return _cache_set(cache_key, get_demo_bundle(ticker)["data"], ttl_seconds=180)
            return _cache_set(cache_key, {
                "ticker": ticker.upper(),
                "company_name": profile["company_name"],
                "sector": profile["sector"],
                "current_price": None,
                "previous_close": None,
                "regular_market_change": 0.0,
                "regular_market_change_percent": 0.0,
                "market_cap": "N/A",
                "pe_ratio": "N/A",
                "div_yield": "N/A",
                "fifty_two_week_high": "N/A",
                "data_source": "unavailable",
                "status_message": "Live data is currently unavailable from Yahoo Finance.",
            }, ttl_seconds=30)

        change = float(current_price) - float(previous_close or current_price)
        change_percent = (change / float(previous_close)) * 100 if previous_close else 0.0

        market_cap = info.get("marketCap") or fast_info.get("marketCap")
        fifty_two_week_high = (
            info.get("fiftyTwoWeekHigh")
            or fast_info.get("yearHigh")
            or (float(hist_1y["High"].max()) if has_hist_1y and "High" in hist_1y else None)
        )
        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        dividend_yield = info.get("dividendYield")

        data_source = "live" if info or fast_info else "history_fallback"
        if data_source == "live":
            status_message = "Showing live market data."
        elif _is_market_closed_context():
            status_message = "Market is closed, showing the last available trading session."
        else:
            status_message = "Showing price-derived fallback data because Yahoo fundamentals were unavailable."

        return _cache_set(cache_key, {
            "ticker": ticker.upper(),
            "company_name": profile["company_name"],
            "sector": profile["sector"],
            "current_price": round(float(current_price), 2),
            "previous_close": round(float(previous_close or current_price), 2),
            "regular_market_change": round(change, 2),
            "regular_market_change_percent": round(change_percent, 2),
            "market_cap": _format_market_cap(market_cap),
            "pe_ratio": round(float(pe_ratio), 2) if pe_ratio not in (None, "", "N/A") else "N/A",
            "div_yield": f"{float(dividend_yield) * 100:.2f}%" if dividend_yield not in (None, "", "N/A") else "N/A",
            "fifty_two_week_high": round(float(fifty_two_week_high), 2) if fifty_two_week_high else "N/A",
            "data_source": data_source,
            "status_message": status_message,
        }, ttl_seconds=45)
    except Exception as e:
        if has_demo_data(ticker):
            return _cache_set(f"data::{ticker.upper()}", get_demo_bundle(ticker)["data"], ttl_seconds=180)
        raise HTTPException(status_code=500, detail=f"Market data fetch error: {str(e)}")


@router.get("/historical", response_model=List[Dict[str, Any]])
def get_historical_data(ticker: str, period: str = "6mo", current_user=Depends(deps.get_current_user)) -> Any:
    """
    Fetch historical OHLCV data for the candlestick chart.
    """
    try:
        cache_key = f"historical::{ticker.upper()}::{period}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        stock = yf.Ticker(ticker)
        hist = _safe_history(stock, period)
        if hist is None or hist.empty:
            if has_demo_data(ticker):
                return get_demo_bundle(ticker)["historical"]
            return []

        chart_data = []
        for date_obj, row in hist.iterrows():
            chart_data.append(
                {
                    "time": date_obj.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                }
            )

        return _cache_set(cache_key, chart_data, ttl_seconds=120)
    except Exception:
        if has_demo_data(ticker):
            return get_demo_bundle(ticker)["historical"]
        return []


@router.get("/news", response_model=List[Dict[str, Any]])
def get_market_news(ticker: str, current_user=Depends(deps.get_current_user)) -> Any:
    """
    Lightweight sentiment tagging for ticker headlines.
    """
    try:
        cache_key = f"news::{ticker.upper()}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        stock = yf.Ticker(ticker)
        raw_news = getattr(stock, "news", []) or []
        formatted_news = []

        for n in raw_news[:4]:
            title = n.get("title", "Market Update")
            sentiment_tag = "NEUTRAL"
            if any(word in title.upper() for word in ["UP", "JUMP", "SOAR", "GAIN", "PROFIT", "GROWTH", "BUY"]):
                sentiment_tag = "POSITIVE"
            elif any(word in title.upper() for word in ["DOWN", "FALL", "PLUNGE", "LOSS", "DEBT", "CRASH", "SELL"]):
                sentiment_tag = "NEGATIVE"

            formatted_news.append(
                {
                    "title": title,
                    "link": n.get("link", "#"),
                    "publisher": n.get("publisher", "Financial Press"),
                    "sentiment": sentiment_tag,
                    "timestamp": n.get("providerPublishTime"),
                }
            )

        if not formatted_news and has_demo_data(ticker):
            return _cache_set(cache_key, get_demo_bundle(ticker)["news"], ttl_seconds=180)
        return _cache_set(cache_key, formatted_news, ttl_seconds=180)
    except Exception:
        if has_demo_data(ticker):
            return _cache_set(f"news::{ticker.upper()}", get_demo_bundle(ticker)["news"], ttl_seconds=180)
        return []


@router.get("/prediction", response_model=Dict[str, Any])
def get_prediction_bounds(
    ticker: str,
    current_price: float | None = None,
    sentiment: str = "NEUTRAL",
    horizon: str = "1d",
    current_user=Depends(deps.get_current_user),
) -> Any:
    """
    Real-time multi-agent prediction endpoint.
    Kept backward compatible with legacy query params.
    """
    try:
        return coordinator.process_ticker(ticker=ticker, horizon=horizon)
    except Exception as e:
        if has_demo_data(ticker):
            demo_prediction = get_demo_bundle(ticker)["prediction"].copy()
            demo_prediction["time_horizon"] = horizon
            return demo_prediction
        raise HTTPException(status_code=500, detail=f"Multi-agent prediction error: {str(e)}")


@router.get("/realtime-analysis", response_model=Dict[str, Any])
def get_realtime_analysis(
    ticker: str,
    horizon: str = "1d",
    current_user=Depends(deps.get_current_user),
) -> Any:
    """
    Explicit real-time analysis route returning full multi-agent output.
    """
    try:
        return coordinator.process_ticker(ticker=ticker, horizon=horizon)
    except Exception as e:
        if has_demo_data(ticker):
            demo_prediction = get_demo_bundle(ticker)["prediction"].copy()
            demo_prediction["time_horizon"] = horizon
            return demo_prediction
        raise HTTPException(status_code=500, detail=f"Realtime analysis error: {str(e)}")

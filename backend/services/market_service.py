from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any, Dict, List, Optional
from cachetools import TTLCache
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from agents.coordinator_agent import CoordinatorAgent
from core.demo_data import get_demo_bundle, has_demo_data, supported_demo_tickers
from core.news_data import get_live_news_headlines
from core.upstox_data import get_full_market_quote, get_historical_candles, has_upstox_config, resolve_instrument, search_instruments

logger = logging.getLogger(__name__)

# Cache setup
_CACHE_TTL_SECONDS = 120
_memory_cache: TTLCache = TTLCache(maxsize=512, ttl=_CACHE_TTL_SECONDS)

# Sentiment Analyzer
_sentiment_analyzer = SentimentIntensityAnalyzer()

# Static Data
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

def _cache_get(key: str):
    return _memory_cache.get(key)

def _cache_set(key: str, value: Any, ttl_seconds: int = _CACHE_TTL_SECONDS) -> Any:
    _memory_cache[key] = value
    return value

# Helpers

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

def _safe_history(stock: yf.Ticker, period: str, interval: str | None = None):
    try:
        kwargs = {"period": period}
        if interval:
            kwargs["interval"] = interval
        return stock.history(**kwargs)
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
    return datetime.now().weekday() >= 5

def _period_to_days_back(period: str) -> int:
    mapping = {
        "1mo": 35, "3mo": 100, "6mo": 190, "1y": 380, "2y": 760, "5y": 1900,
    }
    return mapping.get(period, 190)

def _historical_request_config(timeframe: str) -> Dict[str, Any]:
    normalized = (timeframe or "1d").strip().lower()
    mapping = {
        "1d": {
            "label": "1d", "period": "1y", "yfinance_interval": "1d",
            "upstox_interval": "day", "days_back": 380,
        },
        "1h": {
            "label": "1h", "period": "3mo", "yfinance_interval": "60m",
            "upstox_interval": "30minute", "days_back": 100, "resample_minutes": 60,
        },
        "5m": {
            "label": "5m", "period": "1mo", "yfinance_interval": "5m",
            "upstox_interval": "1minute", "days_back": 35, "resample_minutes": 5,
        },
    }
    return mapping.get(normalized, mapping["1d"])

def _format_chart_time(date_obj: Any, timeframe: str) -> str:
    if timeframe == "1d":
        return date_obj.strftime("%Y-%m-%d")
    return date_obj.strftime("%Y-%m-%dT%H:%M:%S")

def _bucket_start(timestamp: datetime, minutes: int) -> datetime:
    floored_minute = (timestamp.minute // minutes) * minutes
    return timestamp.replace(minute=floored_minute, second=0, microsecond=0)

def _aggregate_candles(rows: List[List[Any]], bucket_minutes: int) -> List[Dict[str, Any]]:
    buckets: Dict[datetime, Dict[str, Any]] = {}
    ordered_keys: List[datetime] = []

    for row in rows:
        if len(row) < 6: continue
        try:
            ts = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
            open_price = float(row[1])
            high_price = float(row[2])
            low_price = float(row[3])
            close_price = float(row[4])
        except (TypeError, ValueError):
            continue

        bucket = _bucket_start(ts, bucket_minutes)
        payload = buckets.get(bucket)
        if payload is None:
            payload = {
                "time": bucket.isoformat(),
                "open": round(open_price, 2), "high": round(high_price, 2),
                "low": round(low_price, 2), "close": round(close_price, 2),
            }
            buckets[bucket] = payload
            ordered_keys.append(bucket)
        else:
            payload["high"] = round(max(float(payload["high"]), high_price), 2)
            payload["low"] = round(min(float(payload["low"]), low_price), 2)
            payload["close"] = round(close_price, 2)

    ordered_keys.sort()
    return [buckets[key] for key in ordered_keys]

def _attach_chart_meta(chart_data: List[Dict], provider: str, source_interval: str, requested_interval: str) -> List[Dict]:
    for item in chart_data:
        item["provider"] = provider
        item["source_interval"] = source_interval
        item["requested_interval"] = requested_interval
    return chart_data

def _headline_sentiment(title: str) -> str:
    """Uses VADER sentiment analysis for financial headlines."""
    # VADER is good at short text and social metrics.
    scores = _sentiment_analyzer.polarity_scores(title)
    compound = scores['compound']
    if compound >= 0.05:
        return "POSITIVE"
    elif compound <= -0.05:
        return "NEGATIVE"
    return "NEUTRAL"

# Services

def get_search_suggestions_service(q: str, limit: int = 8) -> List[Dict[str, str]]:
    query = (q or "").strip()
    if len(query) < 2 or ("." in query and len(query) >= 6):
        return []

    cache_key = f"search::{query.lower()}::{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if has_upstox_config():
        suggestions = search_instruments(query, limit=limit)
        if suggestions:
            return _cache_set(cache_key, suggestions, ttl_seconds=120)

    safe_limit = max(1, min(int(limit), 15))
    search = yf.Search(query=query, max_results=safe_limit)
    quotes = getattr(search, "quotes", []) or []

    yf_suggestions: List[Dict[str, str]] = []
    seen = set()
    for item in quotes:
        symbol = (item.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        yf_suggestions.append({
            "symbol": symbol,
            "name": (item.get("shortname") or item.get("longname") or symbol).strip(),
            "exchange": (item.get("exchange") or item.get("exchDisp") or "").strip(),
            "type": (item.get("quoteType") or "").strip(),
        })
        if len(yf_suggestions) >= safe_limit:
            break

    if yf_suggestions:
        return _cache_set(cache_key, yf_suggestions, ttl_seconds=120)

    # Demo Fallback
    lowered_query = query.lower()
    fallback = []
    for symbol in supported_demo_tickers():
        if lowered_query in symbol.lower():
            bundle = get_demo_bundle(symbol)
            fallback.append({
                "symbol": symbol,
                "name": bundle["data"]["company_name"],
                "exchange": "NSE",
                "type": "EQUITY",
            })
    return fallback[:limit]


def get_market_data_service(ticker: str) -> Dict[str, Any]:
    cache_key = f"data::{ticker.upper()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    provider_error = None
    if has_upstox_config() and ticker.upper().endswith((".NS", ".BO")):
        try:
            quote = get_full_market_quote(ticker)
            instrument = quote.get("_instrument", {})
            current_price = (quote.get("last_price") or quote.get("ltp") or quote.get("close") or (quote.get("ohlc") or {}).get("close"))
            previous_close = ((quote.get("ohlc") or {}).get("close") or quote.get("previous_close") or current_price)
            yearly_high = ((quote.get("extended_market_data") or {}).get("high_52_week") or quote.get("high_52_week"))
            market_cap = (quote.get("extended_market_data") or {}).get("market_cap")
            if current_price is not None:
                change = float(current_price) - float(previous_close or current_price)
                change_pct = (change / float(previous_close)) * 100 if previous_close else 0.0
                return _cache_set(cache_key, {
                    "ticker": ticker.upper(),
                    "company_name": instrument.get("name") or instrument.get("trading_symbol") or _resolve_profile(ticker, {})["company_name"],
                    "sector": instrument.get("segment") or _resolve_profile(ticker, {})["sector"],
                    "current_price": round(float(current_price), 2),
                    "previous_close": round(float(previous_close or current_price), 2),
                    "regular_market_change": round(change, 2),
                    "regular_market_change_percent": round(change_pct, 2),
                    "market_cap": _format_market_cap(market_cap),
                    "pe_ratio": "N/A",
                    "div_yield": "N/A",
                    "fifty_two_week_high": round(float(yearly_high), 2) if yearly_high not in (None, "", "N/A") else "N/A",
                    "data_source": "upstox",
                    "status_message": "Showing live market data from Upstox.",
                }, ttl_seconds=45)
            provider_error = f"Upstox returned no usable current price for {ticker}."
        except Exception as exc:
            provider_error = str(exc)

        try:
            instrument = resolve_instrument(ticker)
            day_candles = get_historical_candles(ticker, interval="day", days_back=10)
            if day_candles:
                latest = day_candles[-1]
                previous = day_candles[-2] if len(day_candles) >= 2 else latest
                current_price = float(latest[4])
                previous_close = float(previous[4])
                day_highs = [float(row[2]) for row in day_candles if len(row) >= 3]
                change = current_price - previous_close
                change_pct = (change / previous_close) * 100 if previous_close else 0.0
                return _cache_set(cache_key, {
                    "ticker": ticker.upper(),
                    "company_name": instrument.get("name") or instrument.get("trading_symbol") or _resolve_profile(ticker, {})["company_name"],
                    "sector": instrument.get("segment") or _resolve_profile(ticker, {})["sector"],
                    "current_price": round(current_price, 2),
                    "previous_close": round(previous_close, 2),
                    "regular_market_change": round(change, 2),
                    "regular_market_change_percent": round(change_pct, 2),
                    "market_cap": "N/A",
                    "pe_ratio": "N/A",
                    "div_yield": "N/A",
                    "fifty_two_week_high": round(max(day_highs), 2) if day_highs else "N/A",
                    "data_source": "upstox_history_fallback",
                    "status_message": "Showing Upstox-derived market data from recent live candles.",
                }, ttl_seconds=45)
        except Exception as exc:
            provider_error = provider_error or str(exc)

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
        info.get("currentPrice") or info.get("regularMarketPrice") or fast_info.get("lastPrice")
        or (closes_5d[-1] if closes_5d else None) or (closes_1y[-1] if closes_1y else None)
    )
    previous_close = (
        info.get("previousClose") or fast_info.get("previousClose")
        or (closes_5d[-2] if len(closes_5d) >= 2 else None) or current_price
    )

    if current_price is None:
        return _cache_set(cache_key, {
            "ticker": ticker.upper(),
            "company_name": profile["company_name"], "sector": profile["sector"],
            "current_price": None, "previous_close": None,
            "regular_market_change": 0.0, "regular_market_change_percent": 0.0,
            "market_cap": "N/A", "pe_ratio": "N/A", "div_yield": "N/A", "fifty_two_week_high": "N/A",
            "data_source": "unavailable",
            "status_message": f"Live data is currently unavailable. Last provider error: {provider_error}" if provider_error else "Live data is currently unavailable from the configured providers.",
        }, ttl_seconds=30)

    change = float(current_price) - float(previous_close or current_price)
    change_percent = (change / float(previous_close)) * 100 if previous_close else 0.0
    market_cap = info.get("marketCap") or fast_info.get("marketCap")
    fifty_two_week_high = (info.get("fiftyTwoWeekHigh") or fast_info.get("yearHigh")
                           or (float(hist_1y["High"].max()) if has_hist_1y and "High" in hist_1y else None))
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
        "company_name": profile["company_name"], "sector": profile["sector"],
        "current_price": round(float(current_price), 2),
        "previous_close": round(float(previous_close or current_price), 2),
        "regular_market_change": round(change, 2), "regular_market_change_percent": round(change_percent, 2),
        "market_cap": _format_market_cap(market_cap),
        "pe_ratio": round(float(pe_ratio), 2) if pe_ratio not in (None, "", "N/A") else "N/A",
        "div_yield": f"{float(dividend_yield) * 100:.2f}%" if dividend_yield not in (None, "", "N/A") else "N/A",
        "fifty_two_week_high": round(float(fifty_two_week_high), 2) if fifty_two_week_high else "N/A",
        "data_source": data_source, "status_message": status_message,
    }, ttl_seconds=45)


def get_historical_data_service(ticker: str, period: str, interval: str) -> List[Dict[str, Any]]:
    request_cfg = _historical_request_config(interval)
    resolved_period = request_cfg["period"] if interval != "1d" else period
    cache_key = f"historical::{ticker.upper()}::{resolved_period}::{request_cfg['label']}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    upstox_interval = request_cfg["upstox_interval"]
    if has_upstox_config() and upstox_interval and ticker.upper().endswith((".NS", ".BO")):
        days_back = _period_to_days_back(resolved_period) if request_cfg["label"] == "1d" else request_cfg["days_back"]
        candles = get_historical_candles(ticker, interval=upstox_interval, days_back=days_back)
        resample_minutes = request_cfg.get("resample_minutes")
        if resample_minutes:
            chart_data = _aggregate_candles(candles, int(resample_minutes))
        else:
            chart_data = []
            for row in candles:
                if len(row) < 6: continue
                chart_data.append({
                    "time": str(row[0])[:19], "open": round(float(row[1]), 2), "high": round(float(row[2]), 2),
                    "low": round(float(row[3]), 2), "close": round(float(row[4]), 2),
                })
        if chart_data:
            chart_data = _attach_chart_meta(chart_data, provider="upstox", source_interval=upstox_interval, requested_interval=request_cfg["label"])
            return _cache_set(cache_key, chart_data, ttl_seconds=120)

    stock = yf.Ticker(ticker)
    hist = _safe_history(stock, resolved_period, request_cfg["yfinance_interval"])
    if hist is None or hist.empty:
        return []

    chart_data = []
    for date_obj, row in hist.iterrows():
        chart_data.append({
            "time": _format_chart_time(date_obj, request_cfg["label"]),
            "open": round(float(row["Open"]), 2), "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2), "close": round(float(row["Close"]), 2),
        })

    chart_data = _attach_chart_meta(chart_data, provider="yahoo", source_interval=request_cfg["yfinance_interval"], requested_interval=request_cfg["label"])
    return _cache_set(cache_key, chart_data, ttl_seconds=120)


def get_market_news_service(ticker: str) -> List[Dict[str, Any]]:
    cache_key = f"news::{ticker.upper()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    formatted_news = []
    for n in get_live_news_headlines(ticker, limit=4):
        title = n.get("title", "Market Update")
        formatted_news.append({
            "title": title,
            "link": n.get("link", "#"),
            "publisher": n.get("publisher", "Financial Press"),
            "sentiment": _headline_sentiment(title),
            "timestamp": n.get("providerPublishTime"),
        })

    return _cache_set(cache_key, formatted_news, ttl_seconds=180)

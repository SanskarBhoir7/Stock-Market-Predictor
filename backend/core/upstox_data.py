from __future__ import annotations

import gzip
import json
from datetime import date, timedelta
from io import BytesIO
from typing import Any, Dict, List
from urllib.parse import quote
from urllib.request import Request, urlopen

from core.config import settings

_instrument_cache: Dict[str, Dict[str, Any]] = {}


def has_upstox_config() -> bool:
    return bool(settings.UPSTOX_ACCESS_TOKEN.strip())


def _json_request(url: str, auth: bool = True) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": "AITradingEngine/1.0",
    }
    if auth:
        headers["Authorization"] = f"Bearer {settings.UPSTOX_ACCESS_TOKEN}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _gzip_json_request(url: str) -> Any:
    request = Request(url, headers={"User-Agent": "AITradingEngine/1.0"})
    with urlopen(request, timeout=30) as response:
        raw = response.read()
    with gzip.GzipFile(fileobj=BytesIO(raw)) as gz:
        return json.loads(gz.read().decode("utf-8"))


def _load_instruments(exchange: str) -> Dict[str, Any]:
    exchange = exchange.upper()
    cached = _instrument_cache.get(exchange)
    if cached is not None:
        return cached

    url = settings.UPSTOX_NSE_INSTRUMENTS_URL if exchange == "NSE" else settings.UPSTOX_BSE_INSTRUMENTS_URL
    records = _gzip_json_request(url)
    mapping: Dict[str, Any] = {}
    for item in records:
        if item.get("segment") not in {"NSE_EQ", "BSE_EQ"}:
            continue
        trading_symbol = (item.get("trading_symbol") or "").strip().upper()
        if not trading_symbol:
            continue
        mapping[trading_symbol] = item
    _instrument_cache[exchange] = mapping
    return mapping


def warm_instrument_cache() -> None:
    for exchange in ("NSE", "BSE"):
        try:
            _load_instruments(exchange)
        except Exception:
            continue


def resolve_instrument(ticker: str) -> Dict[str, Any]:
    normalized = (ticker or "").strip().upper()
    if normalized.endswith(".NS"):
        exchange = "NSE"
        trading_symbol = normalized[:-3]
    elif normalized.endswith(".BO"):
        exchange = "BSE"
        trading_symbol = normalized[:-3]
    else:
        raise RuntimeError(f"Unsupported Upstox ticker format: {ticker}")

    instruments = _load_instruments(exchange)
    instrument = instruments.get(trading_symbol)
    if not instrument:
        raise RuntimeError(f"Instrument not found in Upstox {exchange} instruments file for {ticker}")
    return instrument


def search_instruments(query: str, limit: int = 8) -> List[Dict[str, str]]:
    query = (query or "").strip().upper()
    if not query:
        return []
    matches: List[Dict[str, str]] = []
    for exchange, suffix in (("NSE", ".NS"), ("BSE", ".BO")):
        instruments = _load_instruments(exchange)
        for trading_symbol, item in instruments.items():
            name = (item.get("name") or "").upper()
            if query not in trading_symbol and query not in name:
                continue
            matches.append(
                {
                    "symbol": f"{trading_symbol}{suffix}",
                    "name": item.get("name") or trading_symbol,
                    "exchange": exchange,
                    "type": "EQUITY",
                }
            )
            if len(matches) >= limit:
                return matches
    return matches


def get_full_market_quote(ticker: str) -> Dict[str, Any]:
    instrument = resolve_instrument(ticker)
    instrument_key = instrument["instrument_key"]
    url = f"{settings.UPSTOX_BASE_URL.rstrip('/')}/v2/market-quote/quotes?instrument_key={quote(instrument_key, safe='')}"
    payload = _json_request(url, auth=True)
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    quote_payload = next(iter(data.values()), {})
    if not quote_payload:
        raise RuntimeError(f"Upstox returned no quote data for {ticker}")
    quote_payload["_instrument"] = instrument
    return quote_payload


def get_historical_candles(ticker: str, interval: str = "day", days_back: int = 365) -> List[List[Any]]:
    instrument = resolve_instrument(ticker)
    instrument_key = instrument["instrument_key"]
    to_date = date.today()
    from_date = to_date - timedelta(days=days_back)
    url = (
        f"{settings.UPSTOX_BASE_URL.rstrip('/')}/v2/historical-candle/"
        f"{quote(instrument_key, safe='')}/{interval}/{to_date.isoformat()}/{from_date.isoformat()}"
    )
    payload = _json_request(url, auth=True)
    candles = payload.get("data", {}).get("candles", []) if isinstance(payload, dict) else []
    return list(reversed(candles)) if isinstance(candles, list) else []

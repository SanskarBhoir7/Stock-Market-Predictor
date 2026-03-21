"""
Real-time multi-agent market coordinator.

This module turns the previous placeholder agent design into a working
signal-fusion pipeline powered by live market feeds.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re
from statistics import mean
from typing import Any, Dict, List, Tuple
import asyncio

import pandas as pd
import yfinance as yf

from core.news_data import get_live_news_headlines
from core.upstox_data import get_full_market_quote, get_historical_candles, has_upstox_config


UTC = timezone.utc
_YAHOO_EXTERNAL_COOLDOWN_UNTIL: datetime | None = None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_pct_change(ticker: str) -> Dict[str, Any]:
    """
    Return a tiny real-time snapshot for a symbol.
    """
    global _YAHOO_EXTERNAL_COOLDOWN_UNTIL
    if has_upstox_config() and ticker.upper().endswith((".NS", ".BO")):
        try:
            quote = get_full_market_quote(ticker)
            current_price = (
                quote.get("last_price")
                or quote.get("ltp")
                or quote.get("close")
                or (quote.get("ohlc") or {}).get("close")
            )
            previous_close = (
                (quote.get("ohlc") or {}).get("close")
                or quote.get("previous_close")
                or current_price
            )
            if current_price is None or previous_close is None:
                raise ValueError("missing quote values")
            change_pct = ((float(current_price) - float(previous_close)) / float(previous_close)) * 100 if float(previous_close) else 0.0
            return {
                "ticker": ticker,
                "status": "OK",
                "change_pct": round(change_pct, 3),
                "last_price": round(float(current_price), 4),
                "timestamp": _utc_now_iso(),
            }
        except Exception:
            return {
                "ticker": ticker,
                "status": "DATA_UNAVAILABLE",
                "change_pct": 0.0,
                "last_price": None,
                "timestamp": _utc_now_iso(),
            }
    if _YAHOO_EXTERNAL_COOLDOWN_UNTIL and datetime.now(UTC) < _YAHOO_EXTERNAL_COOLDOWN_UNTIL:
        return {
            "ticker": ticker,
            "status": "DATA_UNAVAILABLE",
            "change_pct": 0.0,
            "last_price": None,
            "timestamp": _utc_now_iso(),
        }
    try:
        hist = yf.Ticker(ticker).history(period="5d", interval="1d")
        if hist.empty or len(hist["Close"]) < 2:
            return {
                "ticker": ticker,
                "status": "DATA_UNAVAILABLE",
                "change_pct": 0.0,
                "last_price": None,
                "timestamp": _utc_now_iso(),
            }
        closes = hist["Close"].dropna()
        if len(closes) < 2:
            raise ValueError("insufficient close points")
        latest = float(closes.iloc[-1])
        prev = float(closes.iloc[-2])
        change_pct = ((latest - prev) / prev) * 100 if prev else 0.0
        candle_ts = hist.index[-1]
        return {
            "ticker": ticker,
            "status": "OK",
            "change_pct": round(change_pct, 3),
            "last_price": round(latest, 4),
            "timestamp": candle_ts.to_pydatetime().replace(tzinfo=UTC).isoformat(),
        }
    except Exception:
        _YAHOO_EXTERNAL_COOLDOWN_UNTIL = datetime.now(UTC) + timedelta(minutes=10)
        return {
            "ticker": ticker,
            "status": "DATA_UNAVAILABLE",
            "change_pct": 0.0,
            "last_price": None,
            "timestamp": _utc_now_iso(),
        }


def _ticker_history_frame(ticker: str, days_back: int = 190):
    if has_upstox_config() and ticker.upper().endswith((".NS", ".BO")):
        try:
            candles = get_historical_candles(ticker, interval="day", days_back=days_back)
            if not candles:
                raise ValueError("empty candles")
            frame = pd.DataFrame(candles, columns=["datetime", "Open", "High", "Low", "Close", "Volume", "OpenInterest"])
            frame["datetime"] = pd.to_datetime(frame["datetime"])
            frame = frame.set_index("datetime").sort_index()
            for column in ["Open", "High", "Low", "Close", "Volume"]:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            return frame[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        except Exception:
            pass
    return yf.Ticker(ticker).history(period="6mo", interval="1d")


def _vote_from_score(score: float, threshold: float = 0.1) -> str:
    if score > threshold:
        return "Bullish"
    if score < -threshold:
        return "Bearish"
    return "Neutral"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _safe_logit(p: float) -> float:
    p = _clamp(p, 1e-6, 1 - 1e-6)
    return math.log(p / (1 - p))


def _three_way_entropy(p_up: float, p_down: float, p_sideways: float) -> float:
    probs = [max(1e-12, p_up), max(1e-12, p_down), max(1e-12, p_sideways)]
    h = -sum(p * math.log(p) for p in probs)
    return h / math.log(3.0)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z]+", (text or "").lower())


def _normalize_component(value: float, scale: float = 1.0) -> float:
    return _clamp(value / scale, -1.0, 1.0)


def _agent_status(agent_result: Dict[str, Any]) -> str:
    signals = agent_result.get("signals")
    if isinstance(signals, list):
        statuses = [item.get("status") for item in signals if isinstance(item, dict)]
        ok = sum(1 for status in statuses if status == "OK")
        unavailable = sum(1 for status in statuses if status == "DATA_UNAVAILABLE")
        if ok == 0 and unavailable > 0:
            return "UNAVAILABLE"
        if unavailable > 0:
            return "PARTIAL"
    elif isinstance(signals, dict):
        nested = [value.get("status") for value in signals.values() if isinstance(value, dict)]
        if signals.get("status") == "DATA_UNAVAILABLE":
            return "UNAVAILABLE"
        ok = sum(1 for status in nested if status == "OK")
        unavailable = sum(1 for status in nested if status == "DATA_UNAVAILABLE")
        if ok == 0 and unavailable > 0:
            return "UNAVAILABLE"
        if unavailable > 0:
            return "PARTIAL"

    if agent_result.get("agent") == "News-Sentiment" and int(agent_result.get("headline_count", 0)) == 0:
        return "UNAVAILABLE"
    return "LIVE"


def _mean_age_hours(agent_result: Dict[str, Any]) -> float | None:
    """
    Estimate data recency for an agent by inspecting signal/headline timestamps.
    """
    now = datetime.now(UTC)
    ages: List[float] = []

    signals = agent_result.get("signals")
    if isinstance(signals, list):
        for item in signals:
            if isinstance(item, dict):
                ts = item.get("timestamp")
                if isinstance(ts, str):
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        ages.append(max(0.0, (now - dt.astimezone(UTC)).total_seconds() / 3600.0))
                    except ValueError:
                        continue
    elif isinstance(signals, dict):
        for item in signals.values():
            if isinstance(item, dict):
                ts = item.get("timestamp")
                if isinstance(ts, str):
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        ages.append(max(0.0, (now - dt.astimezone(UTC)).total_seconds() / 3600.0))
                    except ValueError:
                        continue

    # Yahoo headline timestamps are epoch seconds.
    for item in agent_result.get("top_headlines", []):
        ts = item.get("timestamp")
        if isinstance(ts, (int, float)) and ts > 0:
            dt = datetime.fromtimestamp(float(ts), tz=UTC)
            ages.append(max(0.0, (now - dt).total_seconds() / 3600.0))

    return mean(ages) if ages else None


def _agent_reliability(agent_result: Dict[str, Any]) -> float:
    """
    Reliability score in [0.35, 1.0] based on missing data and sample depth.
    """
    base = 1.0
    signals = agent_result.get("signals")
    if isinstance(signals, list) and signals:
        missing = sum(1 for x in signals if isinstance(x, dict) and x.get("status") == "DATA_UNAVAILABLE")
        base -= 0.4 * (missing / len(signals))
    elif isinstance(signals, dict):
        nested = [v for v in signals.values() if isinstance(v, dict)]
        if nested:
            missing = sum(1 for x in nested if x.get("status") == "DATA_UNAVAILABLE")
            base -= 0.4 * (missing / len(nested))
        elif signals.get("status") == "DATA_UNAVAILABLE":
            base -= 0.5

    if agent_result.get("agent") == "News-Sentiment":
        headline_count = int(agent_result.get("headline_count", 0))
        if headline_count == 0:
            base -= 0.45
        elif headline_count < 3:
            base -= 0.2

    return _clamp(base, 0.35, 1.0)


def _agent_freshness(agent_result: Dict[str, Any]) -> float:
    """
    Freshness decay: exp(-age_hours / tau), clipped to [0.45, 1.0].
    """
    age_hours = _mean_age_hours(agent_result)
    if age_hours is None:
        # Technical data may not carry explicit timestamps in our payload.
        return 0.9 if agent_result.get("agent") == "Technical-Flow" else 0.75
    return _clamp(math.exp(-age_hours / 72.0), 0.45, 1.0)


def _horizon_days(horizon: str) -> float:
    mapping = {
        "1h": 1.0 / 6.0,   # approx one trading hour
        "4h": 4.0 / 6.0,
        "1d": 1.0,
        "3d": 3.0,
        "1w": 5.0,
    }
    return mapping.get(horizon, 1.0)


class MacroGeopoliticsAgent:
    def analyze(self, headlines: List[str]) -> Dict[str, Any]:
        risk_tickers = ["^GSPC", "^IXIC", "^DJI", "^NSEI", "^VIX"]
        snaps = [_safe_pct_change(t) for t in risk_tickers]
        equity_moves = [s["change_pct"] for s in snaps if s["status"] == "OK" and s["ticker"] != "^VIX"]
        vix_move = next((s["change_pct"] for s in snaps if s["ticker"] == "^VIX"), 0.0)

        macro_score = mean(equity_moves) / 2.0 if equity_moves else 0.0
        macro_score += (-vix_move / 3.5)

        geo_negative = ("war", "sanction", "conflict", "attack", "tariff", "strike", "missile")
        geo_positive = ("ceasefire", "deal", "truce", "agreement", "rate cut", "stimulus")
        joined = " ".join(h.lower() for h in headlines[:12])
        macro_score -= 0.6 if any(k in joined for k in geo_negative) else 0.0
        macro_score += 0.4 if any(k in joined for k in geo_positive) else 0.0

        vote = _vote_from_score(macro_score, threshold=0.15)
        live_signal_count = sum(1 for s in snaps if s["status"] == "OK")
        return {
            "agent": "Macro-Geopolitics",
            "vote": vote,
            "score": round(_clamp(macro_score, -1.0, 1.0), 3),
            "reason": "Derived from global index breadth, VIX move, and geopolitical keywords.",
            "signals": snaps,
            "insight": {
                "title": "Macro Regime",
                "summary": (
                    f"{vote} backdrop from global equities and volatility gauges."
                    if live_signal_count
                    else "Macro inputs are currently unavailable, so this agent has minimal influence."
                ),
                "details": [
                    f"Global equity breadth: {round(mean(equity_moves), 2)}%" if equity_moves else "Global equity breadth unavailable.",
                    f"VIX move: {round(vix_move, 2)}%",
                    f"Headline shock filter scanned {min(len(headlines), 12)} recent headlines.",
                ],
            },
            "status": "LIVE" if live_signal_count == len(snaps) else "PARTIAL" if live_signal_count else "UNAVAILABLE",
        }


class CommoditiesFxAgent:
    def analyze(self) -> Dict[str, Any]:
        basket = {
            "CRUDE": "CL=F",
            "GOLD": "GC=F",
            "SILVER": "SI=F",
            "NATGAS": "NG=F",
            "USDINR": "INR=X",
            "DXY": "DX-Y.NYB",
            "US10Y": "^TNX",
        }
        snaps = {name: _safe_pct_change(sym) for name, sym in basket.items()}

        # For India equities: higher crude/USDINR/yields are usually headwinds.
        score = 0.0
        if snaps["CRUDE"]["status"] == "OK":
            score += -0.35 * (snaps["CRUDE"]["change_pct"] / 1.5)
        if snaps["USDINR"]["status"] == "OK":
            score += -0.4 * (snaps["USDINR"]["change_pct"] / 0.8)
        if snaps["DXY"]["status"] == "OK":
            score += -0.2 * (snaps["DXY"]["change_pct"] / 0.7)
        if snaps["US10Y"]["status"] == "OK":
            score += -0.2 * (snaps["US10Y"]["change_pct"] / 1.0)
        if snaps["GOLD"]["status"] == "OK":
            score += -0.1 * (snaps["GOLD"]["change_pct"] / 1.0)

        vote = _vote_from_score(score, threshold=0.12)
        live_signal_count = sum(1 for s in snaps.values() if s["status"] == "OK")
        return {
            "agent": "Commodities-FX",
            "vote": vote,
            "score": round(_clamp(score, -1.0, 1.0), 3),
            "reason": "Built from crude, USDINR, DXY, US10Y and defensive metal moves.",
            "signals": snaps,
            "insight": {
                "title": "Cross-Asset Pressure",
                "summary": (
                    f"{vote} pressure from crude, FX, yields, and defensive assets."
                    if live_signal_count
                    else "Cross-asset inputs are currently unavailable, so this agent has minimal influence."
                ),
                "details": [
                    f"USDINR change: {snaps['USDINR']['change_pct']}%" if snaps["USDINR"]["status"] == "OK" else "USDINR unavailable.",
                    f"Crude change: {snaps['CRUDE']['change_pct']}%" if snaps["CRUDE"]["status"] == "OK" else "Crude unavailable.",
                    f"US10Y change: {snaps['US10Y']['change_pct']}%" if snaps["US10Y"]["status"] == "OK" else "US10Y unavailable.",
                ],
            },
            "status": "LIVE" if live_signal_count == len(snaps) else "PARTIAL" if live_signal_count else "UNAVAILABLE",
        }


class NewsSentimentAgent:
    POSITIVE_WORDS = {
        "beat",
        "surge",
        "growth",
        "buy",
        "upgrade",
        "record",
        "strong",
        "profit",
        "rise",
        "gain",
    }
    NEGATIVE_WORDS = {
        "miss",
        "downgrade",
        "fall",
        "drop",
        "loss",
        "fraud",
        "probe",
        "lawsuit",
        "debt",
        "sell",
        "plunge",
    }
    SEVERE_WORDS = {"bankruptcy", "default", "war", "sanction", "crash", "ban"}

    def analyze(self, ticker: str) -> Dict[str, Any]:
        raw_news = get_live_news_headlines(ticker, limit=10)

        scored_items: List[Dict[str, Any]] = []
        total = 0.0
        severe = 0
        for item in raw_news[:10]:
            title = (item.get("title") or "").strip()
            tokens = _tokenize(title)
            token_set = set(tokens)
            pos = sum(w in token_set for w in self.POSITIVE_WORDS)
            neg = sum(w in token_set for w in self.NEGATIVE_WORDS)
            sev = any(w in token_set for w in self.SEVERE_WORDS)
            score = float(pos - neg)
            if sev:
                score -= 0.8
                severe += 1
            scored_items.append(
                {
                    "title": title,
                    "publisher": item.get("publisher", "Unknown"),
                    "timestamp": item.get("providerPublishTime"),
                    "score": round(score, 3),
                    "sentiment": "POSITIVE" if score > 0.2 else "NEGATIVE" if score < -0.2 else "NEUTRAL",
                }
            )
            total += score

        normalized = total / max(len(scored_items), 1)
        vote = _vote_from_score(normalized, threshold=0.2)
        return {
            "agent": "News-Sentiment",
            "vote": vote,
            "score": round(normalized, 3),
            "reason": "Headline-level lexical sentiment with severe-event penalties.",
            "headline_count": len(scored_items),
            "severe_negative_count": severe,
            "top_headlines": scored_items[:5],
            "insight": {
                "title": "News Sentiment",
                "summary": (
                    f"{vote} from {len(scored_items)} recent headlines."
                    if scored_items
                    else "No live headlines were available, so sentiment contribution is weak."
                ),
                "details": [
                    f"Average headline score: {round(normalized, 2)}",
                    f"Severe negative headlines: {severe}",
                    f"Top publisher: {scored_items[0]['publisher']}" if scored_items else "Publisher mix unavailable.",
                ],
            },
            "status": "LIVE" if scored_items else "UNAVAILABLE",
        }


class TechnicalFlowAgent:
    def analyze(self, ticker: str) -> Dict[str, Any]:
        try:
            hist = _ticker_history_frame(ticker, days_back=190)
            if hist.empty or len(hist) < 60:
                raise ValueError("insufficient history")
        except Exception:
            return {
                "agent": "Technical-Flow",
                "vote": "Neutral",
                "score": 0.0,
                "reason": "DATA_UNAVAILABLE for technical history window.",
                "signals": {"status": "DATA_UNAVAILABLE"},
            }

        close = hist["Close"].dropna()
        vol = hist["Volume"].dropna()
        latest_close = float(close.iloc[-1])
        sma20 = float(close.tail(20).mean())
        sma50 = float(close.tail(50).mean())
        ret_5 = float(((latest_close / float(close.iloc[-6])) - 1.0) * 100.0) if len(close) >= 6 and float(close.iloc[-6]) else 0.0
        ret_20 = float(((latest_close / float(close.iloc[-21])) - 1.0) * 100.0) if len(close) >= 21 and float(close.iloc[-21]) else 0.0
        ret = close.diff()
        up = ret.clip(lower=0).rolling(14).mean()
        down = (-ret.clip(upper=0)).rolling(14).mean()
        rs = (up / down).fillna(0)
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        avg_vol20 = float(vol.tail(20).mean()) if len(vol) >= 20 else float(vol.mean())
        vol_spike = float(vol.iloc[-1] / avg_vol20) if avg_vol20 else 1.0
        breakout = latest_close > float(close.tail(20).max() * 0.995)
        pullback = latest_close < float(close.tail(20).min() * 1.015)

        score = 0.0
        score += 0.45 if sma20 > sma50 else -0.45
        score += 0.35 if latest_close > sma20 else -0.35
        score += _clamp(ret_5 / 4.0, -0.35, 0.35)
        score += _clamp(ret_20 / 7.5, -0.45, 0.45)
        if rsi > 70:
            score -= 0.2
        elif rsi < 30:
            score += 0.2
        score += 0.25 if breakout else 0.0
        score -= 0.2 if pullback else 0.0
        score += 0.15 if vol_spike > 1.2 else 0.0

        vote = _vote_from_score(score, threshold=0.2)
        return {
            "agent": "Technical-Flow",
            "vote": vote,
            "score": round(_clamp(score, -1.0, 1.0), 3),
            "reason": "Trend, RSI regime, breakout context, and volume confirmation.",
            "signals": {
                "latest_close": round(latest_close, 3),
                "sma20": round(sma20, 3),
                "sma50": round(sma50, 3),
                "ret_5d_pct": round(ret_5, 2),
                "ret_20d_pct": round(ret_20, 2),
                "rsi14": round(rsi, 2),
                "volume_spike_x": round(vol_spike, 2),
                "breakout_context": breakout,
                "pullback_context": pullback,
            },
            "insight": {
                "title": "Technical Flow",
                "summary": f"{vote} technical setup from trend, momentum, and participation.",
                "details": [
                    f"SMA20 vs SMA50: {round(sma20, 2)} vs {round(sma50, 2)}",
                    f"5D/20D return: {round(ret_5, 2)}% / {round(ret_20, 2)}%",
                    f"RSI(14): {round(rsi, 2)}",
                    f"Volume spike: {round(vol_spike, 2)}x",
                ],
            },
            "status": "LIVE",
        }


class FundamentalsAgent:
    def analyze(self, ticker: str) -> Dict[str, Any]:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            fast_info = dict(stock.fast_info.items()) if hasattr(stock.fast_info, "items") else {}
            hist = _ticker_history_frame(ticker, days_back=260)
        except Exception:
            info = {}
            fast_info = {}
            hist = pd.DataFrame()

        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        dividend_yield = info.get("dividendYield")
        market_cap = info.get("marketCap") or fast_info.get("marketCap")
        year_high = info.get("fiftyTwoWeekHigh") or fast_info.get("yearHigh")
        year_low = info.get("fiftyTwoWeekLow") or fast_info.get("yearLow")

        close = hist["Close"].dropna() if not hist.empty and "Close" in hist else pd.Series(dtype=float)
        latest_close = float(close.iloc[-1]) if len(close) else None
        returns = close.pct_change().dropna() if len(close) > 5 else pd.Series(dtype=float)
        volatility_20d = float(returns.tail(20).std()) if len(returns) >= 20 else None

        valuation_component = 0.0
        if pe_ratio not in (None, "", "N/A"):
            pe = float(pe_ratio)
            if pe <= 18:
                valuation_component = 0.35
            elif pe <= 28:
                valuation_component = 0.15
            elif pe <= 40:
                valuation_component = -0.05
            else:
                valuation_component = -0.25

        income_component = 0.0
        if dividend_yield not in (None, "", "N/A"):
            income_component = _clamp(float(dividend_yield) * 8.0, -0.05, 0.2)

        size_component = 0.0
        if market_cap not in (None, "", "N/A"):
            cap = float(market_cap)
            if cap >= 1_000_000_000_000:
                size_component = 0.2
            elif cap >= 300_000_000_000:
                size_component = 0.1

        range_component = 0.0
        if latest_close and year_high and year_low and float(year_high) > float(year_low):
            position = (latest_close - float(year_low)) / (float(year_high) - float(year_low))
            range_component = _normalize_component(position - 0.5, 0.5) * 0.2

        stability_component = 0.0
        if volatility_20d is not None:
            stability_component = -_clamp(volatility_20d * 8.0, 0.0, 0.2)

        score = _clamp(
            valuation_component + income_component + size_component + range_component + stability_component,
            -1.0,
            1.0,
        )
        vote = _vote_from_score(score, threshold=0.12)

        details = [
            f"PE ratio: {round(float(pe_ratio), 2)}" if pe_ratio not in (None, "", "N/A") else "PE ratio unavailable.",
            (
                f"Dividend yield: {round(float(dividend_yield) * 100, 2)}%"
                if dividend_yield not in (None, "", "N/A")
                else "Dividend yield unavailable."
            ),
            f"Market cap: {round(float(market_cap) / 1_000_000_000_000, 2)}T" if market_cap not in (None, "", "N/A") else "Market cap unavailable.",
            f"20D volatility: {round(volatility_20d * 100, 2)}%" if volatility_20d is not None else "20D volatility unavailable.",
        ]

        return {
            "agent": "Fundamentals",
            "vote": vote,
            "score": round(score, 3),
            "reason": "Formula blend of valuation, income, size, range position, and volatility stability.",
            "signals": {
                "pe_ratio": {"value": round(float(pe_ratio), 3), "status": "OK"} if pe_ratio not in (None, "", "N/A") else {"status": "DATA_UNAVAILABLE"},
                "dividend_yield": {"value": round(float(dividend_yield) * 100, 3), "status": "OK"} if dividend_yield not in (None, "", "N/A") else {"status": "DATA_UNAVAILABLE"},
                "market_cap": {"value": float(market_cap), "status": "OK"} if market_cap not in (None, "", "N/A") else {"status": "DATA_UNAVAILABLE"},
                "volatility_20d": {"value": round(volatility_20d, 6), "status": "OK"} if volatility_20d is not None else {"status": "DATA_UNAVAILABLE"},
            },
            "formula_inputs": {
                "valuation_component": round(valuation_component, 3),
                "income_component": round(income_component, 3),
                "size_component": round(size_component, 3),
                "range_component": round(range_component, 3),
                "stability_component": round(stability_component, 3),
            },
            "insight": {
                "title": "Fundamentals",
                "summary": f"{vote} fundamental backdrop from valuation, quality, and stability factors.",
                "details": details,
            },
            "status": "LIVE" if any("unavailable" not in d.lower() for d in details) else "PARTIAL",
        }


class RiskManagerAgent:
    def synthesize(
        self,
        ticker: str,
        current_price: float,
        horizon: str,
        agent_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        base_weights = {
            "Macro-Geopolitics": 0.12,
            "Commodities-FX": 0.10,
            "News-Sentiment": 0.23,
            "Technical-Flow": 0.33,
            "Fundamentals": 0.22,
        }

        # 1) Convert each agent score into calibrated direction probability.
        # p_i(up) = sigmoid(k * clamp(score_i, -2.5, 2.5))
        evidence_log_odds = 0.0
        effective_weights: Dict[str, float] = {}
        weighted_score = 0.0
        freshness_terms: List[float] = []
        reliability_terms: List[float] = []
        active_results: List[Dict[str, Any]] = []
        total_effective_weight = 0.0
        for result in agent_results:
            agent = result["agent"]
            score_i = float(result.get("score", 0.0))
            p_i_up = _sigmoid(1.25 * _clamp(score_i, -2.5, 2.5))
            status = result.get("status", _agent_status(result))

            reliability = _agent_reliability(result)
            freshness = _agent_freshness(result)
            if status == "UNAVAILABLE":
                effective_weights[agent] = 0.0
                continue
            if status == "PARTIAL":
                reliability *= 0.7

            w_eff = base_weights.get(agent, 0.0) * reliability * freshness
            effective_weights[agent] = round(w_eff, 4)
            if w_eff <= 0:
                continue

            reliability_terms.append(reliability)
            freshness_terms.append(freshness)
            active_results.append(result)
            total_effective_weight += w_eff

            evidence_log_odds += w_eff * _safe_logit(p_i_up)
            weighted_score += w_eff * score_i

        # 2) Fused directional probability via weighted log-odds.
        normalized_log_odds = evidence_log_odds / max(total_effective_weight, 1e-6)
        p_up_raw = _sigmoid(1.6 * normalized_log_odds)

        votes = [r["vote"] for r in active_results]
        agreement = max(votes.count("Bullish"), votes.count("Bearish"), votes.count("Neutral")) / max(len(votes), 1)
        avg_freshness = mean(freshness_terms) if freshness_terms else 0.75
        avg_reliability = mean(reliability_terms) if reliability_terms else 0.75
        signal_strength = _clamp(total_effective_weight / sum(base_weights.values()), 0.0, 1.0)

        # 3) Build SIDEWAYS probability from uncertainty and disagreement.
        directional_uncertainty = 1.0 - abs(2.0 * p_up_raw - 1.0)  # high when p_up_raw ~= 0.5
        p_sideways = _clamp(
            0.03 + 0.28 * directional_uncertainty + 0.16 * (1.0 - agreement) + 0.12 * (1.0 - signal_strength),
            0.03,
            0.62,
        )

        trend_mass = 1.0 - p_sideways
        p_up = trend_mass * p_up_raw
        p_down = trend_mass * (1.0 - p_up_raw)

        total_p = p_up + p_down + p_sideways
        p_up, p_down, p_sideways = p_up / total_p, p_down / total_p, p_sideways / total_p

        if p_up >= p_down and p_up >= p_sideways:
            final_call = "UP"
        elif p_down >= p_up and p_down >= p_sideways:
            final_call = "DOWN"
        else:
            final_call = "SIDEWAYS"

        # 4) Confidence from normalized 3-way entropy + data quality factors.
        h_norm = _three_way_entropy(p_up, p_down, p_sideways)
        directional_edge = abs(p_up - p_down)
        missing_penalty = 1.0 - max(0.0, min(0.55, 1.0 - avg_reliability))
        confidence = int(
            round(
                _clamp(
                    100.0
                    * (0.18 + 0.82 * directional_edge)
                    * (0.16 + 0.84 * (1.0 - h_norm))
                    * (0.3 + 0.7 * agreement)
                    * (0.4 + 0.6 * avg_freshness)
                    * (0.35 + 0.65 * avg_reliability)
                    * (0.2 + 0.8 * signal_strength)
                    * missing_penalty,
                    2.0,
                    96.0,
                )
            )
        )

        if final_call == "UP" and confidence >= 44 and p_up >= 0.4:
            decision = "BUY"
        elif final_call == "DOWN" and confidence >= 42 and p_down >= 0.4:
            decision = "NO_BUY"
        else:
            decision = "WAIT"

        # 5) Volatility-scaled probabilistic interval (lognormal approximation).
        horizon_d = _horizon_days(horizon)
        daily_sigma = 0.018
        try:
            hist = _ticker_history_frame(ticker, days_back=190)
            if not hist.empty and len(hist) > 30:
                returns = hist["Close"].pct_change().dropna()
                if len(returns) > 20:
                    daily_sigma = float(returns.std())
        except Exception:
            pass

        sigma_h = max(0.004, daily_sigma * math.sqrt(max(horizon_d, 1e-3)))
        expected_return = (p_up - p_down) * 0.35 * sigma_h
        z_90 = 1.645
        lower = current_price * math.exp(expected_return - z_90 * sigma_h)
        upper = current_price * math.exp(expected_return + z_90 * sigma_h)

        if final_call == "UP":
            invalidation = current_price * math.exp(-0.65 * sigma_h)
        elif final_call == "DOWN":
            invalidation = current_price * math.exp(0.65 * sigma_h)
        else:
            invalidation = current_price

        stop_low = current_price * math.exp(-1.0 * sigma_h)
        stop_high = current_price * math.exp(1.0 * sigma_h)

        return {
            "agent": "Risk-Manager",
            "vote": "Risk-On" if final_call == "UP" else "Risk-Off" if final_call == "DOWN" else "Neutral",
            "weighted_score": round(weighted_score, 3),
            "effective_weights": effective_weights,
            "probabilities": {
                "up": round(p_up, 4),
                "down": round(p_down, 4),
                "sideways": round(p_sideways, 4),
            },
            "final_call": final_call,
            "decision": decision,
            "confidence": confidence,
            "confidence_factors": {
                "agreement": round(agreement, 4),
                "freshness": round(avg_freshness, 4),
                "reliability": round(avg_reliability, 4),
                "entropy": round(h_norm, 4),
                "signal_strength": round(signal_strength, 4),
            },
            "time_horizon": horizon,
            "forecast": {
                "lower_bound": round(lower, 2),
                "upper_bound": round(upper, 2),
            },
            "risk_plan": {
                "invalidation_level": round(invalidation, 2),
                "stop_loss_zone": [round(stop_low, 2), round(stop_high, 2)],
                "risk_alerts": [
                    "Probabilities are entropy-adjusted and fall when agents disagree.",
                    "Confidence degrades when source freshness/reliability falls.",
                    "Macro/geopolitical shocks can still create regime breaks and gap risk.",
                ],
            },
            "insight": {
                "title": "Decision Engine",
                "summary": f"{decision} with {confidence}% confidence for the {horizon} horizon.",
                "details": [
                    f"Final call: {final_call}",
                    f"Probabilities UP/DOWN/SIDEWAYS: {round(p_up, 2)}/{round(p_down, 2)}/{round(p_sideways, 2)}",
                    f"Agreement {round(agreement * 100)}%, reliability {round(avg_reliability * 100)}%, freshness {round(avg_freshness * 100)}%",
                    f"Signal strength {round(signal_strength * 100)}% from {len(active_results)}/{len(agent_results)} active agents.",
                ],
            },
            "status": "LIVE",
        }


class CoordinatorAgent:
    def __init__(self) -> None:
        self.macro_agent = MacroGeopoliticsAgent()
        self.commodities_agent = CommoditiesFxAgent()
        self.sentiment_agent = NewsSentimentAgent()
        self.technical_agent = TechnicalFlowAgent()
        self.fundamentals_agent = FundamentalsAgent()
        self.risk_agent = RiskManagerAgent()

    def _get_current_price(self, ticker: str, fallback_price: float | None = None) -> Tuple[float, str]:
        snap = _safe_pct_change(ticker)
        price = snap.get("last_price")
        if price is None and fallback_price is not None:
            return float(fallback_price), _utc_now_iso()
        if price is None:
            raise ValueError(f"Unable to fetch current price for {ticker}")
        return float(price), snap.get("timestamp", _utc_now_iso())

    def process_ticker(self, ticker: str, horizon: str = "1d", current_price: float | None = None) -> Dict[str, Any]:
        """
        Execute full multi-agent orchestration and return one fused decision object.
        """
        current_price, market_ts = self._get_current_price(ticker, fallback_price=current_price)

        # Use ticker-specific headlines as cross-input for macro and sentiment modules.
        sentiment_result = self.sentiment_agent.analyze(ticker)
        headlines = [h["title"] for h in sentiment_result.get("top_headlines", [])]
        macro_result = self.macro_agent.analyze(headlines)
        commodities_result = self.commodities_agent.analyze()
        technical_result = self.technical_agent.analyze(ticker)
        fundamentals_result = self.fundamentals_agent.analyze(ticker)

        core_results = [macro_result, commodities_result, sentiment_result, technical_result, fundamentals_result]
        risk_result = self.risk_agent.synthesize(ticker, current_price, horizon, core_results)

        missing_data: List[str] = []
        for res in core_results:
            signals = res.get("signals")
            if isinstance(signals, dict):
                for key, value in signals.items():
                    if isinstance(value, dict) and value.get("status") == "DATA_UNAVAILABLE":
                        missing_data.append(f"{res['agent']}::{key}")
            elif isinstance(signals, list):
                for value in signals:
                    if isinstance(value, dict) and value.get("status") == "DATA_UNAVAILABLE":
                        missing_data.append(f"{res['agent']}::{value.get('ticker', 'unknown')}")
            if res.get("headline_count", 1) == 0:
                missing_data.append("News-Sentiment::headlines")

        top_drivers = [
            f"Technical trend vote: {technical_result['vote']} (score={technical_result['score']})",
            f"Macro risk tone: {macro_result['vote']} (score={macro_result['score']})",
            f"Commodities/FX pressure: {commodities_result['vote']} (score={commodities_result['score']})",
            f"News sentiment: {sentiment_result['vote']} (headlines={sentiment_result['headline_count']})",
            f"Fundamentals: {fundamentals_result['vote']} (score={fundamentals_result['score']})",
            (
                "Probabilities (UP/DOWN/SIDEWAYS): "
                f"{risk_result['probabilities']['up']}/"
                f"{risk_result['probabilities']['down']}/"
                f"{risk_result['probabilities']['sideways']}"
            ),
        ]

        return {
            "ticker": ticker.upper(),
            "timestamp": _utc_now_iso(),
            "market_timestamp": market_ts,
            "current_price": round(current_price, 2),
            "final_call": risk_result["final_call"],
            "decision": risk_result["decision"],
            "confidence_score": risk_result["confidence"],
            "time_horizon": risk_result["time_horizon"],
            "lower_bound": risk_result["forecast"]["lower_bound"],
            "upper_bound": risk_result["forecast"]["upper_bound"],
            "model_type": "Multi-Agent Signal Fusion v1",
            "decision_summary": risk_result["insight"]["summary"],
            "top_drivers": top_drivers,
            "agent_votes": {
                "macro_geopolitics": {"vote": macro_result["vote"], "reason": macro_result["reason"]},
                "commodities_fx": {"vote": commodities_result["vote"], "reason": commodities_result["reason"]},
                "news_sentiment": {"vote": sentiment_result["vote"], "reason": sentiment_result["reason"]},
                "technical_flow": {"vote": technical_result["vote"], "reason": technical_result["reason"]},
                "fundamentals": {"vote": fundamentals_result["vote"], "reason": fundamentals_result["reason"]},
                "risk_manager": {"vote": risk_result["vote"], "reason": "Weighted fusion of all agent scores."},
            },
            "probabilities": risk_result["probabilities"],
            "confidence_factors": risk_result["confidence_factors"],
            "risk_plan": risk_result["risk_plan"],
            "missing_data": sorted(set(missing_data)),
            "agent_insights": {
                "macro_geopolitics": macro_result.get("insight", {}),
                "commodities_fx": commodities_result.get("insight", {}),
                "news_sentiment": sentiment_result.get("insight", {}),
                "technical_flow": technical_result.get("insight", {}),
                "fundamentals": fundamentals_result.get("insight", {}),
                "risk_manager": risk_result.get("insight", {}),
            },
            "agent_status": {
                "macro_geopolitics": macro_result.get("status", _agent_status(macro_result)),
                "commodities_fx": commodities_result.get("status", _agent_status(commodities_result)),
                "news_sentiment": sentiment_result.get("status", _agent_status(sentiment_result)),
                "technical_flow": technical_result.get("status", _agent_status(technical_result)),
                "fundamentals": fundamentals_result.get("status", _agent_status(fundamentals_result)),
                "risk_manager": risk_result.get("status", _agent_status(risk_result)),
            },
            "raw_agents": {
                "macro_geopolitics": macro_result,
                "commodities_fx": commodities_result,
                "news_sentiment": sentiment_result,
                "technical_flow": technical_result,
                "fundamentals": fundamentals_result,
                "risk_manager": risk_result,
            },
        }

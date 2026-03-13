"""
Real-time multi-agent market coordinator.

This module turns the previous placeholder agent design into a working
signal-fusion pipeline powered by live yfinance feeds.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Tuple

import yfinance as yf


UTC = timezone.utc


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_pct_change(ticker: str) -> Dict[str, Any]:
    """
    Return a tiny real-time snapshot for a symbol.
    """
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
        return {
            "ticker": ticker,
            "status": "DATA_UNAVAILABLE",
            "change_pct": 0.0,
            "last_price": None,
            "timestamp": _utc_now_iso(),
        }


def _vote_from_score(score: float, threshold: float = 0.1) -> str:
    if score > threshold:
        return "Bullish"
    if score < -threshold:
        return "Bearish"
    return "Neutral"


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
        return {
            "agent": "Macro-Geopolitics",
            "vote": vote,
            "score": round(macro_score, 3),
            "reason": "Derived from global index breadth, VIX move, and geopolitical keywords.",
            "signals": snaps,
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
        return {
            "agent": "Commodities-FX",
            "vote": vote,
            "score": round(score, 3),
            "reason": "Built from crude, USDINR, DXY, US10Y and defensive metal moves.",
            "signals": snaps,
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
        try:
            raw_news = yf.Ticker(ticker).news or []
        except Exception:
            raw_news = []

        scored_items: List[Dict[str, Any]] = []
        total = 0.0
        severe = 0
        for item in raw_news[:10]:
            title = (item.get("title") or "").strip()
            text = title.lower()
            pos = sum(w in text for w in self.POSITIVE_WORDS)
            neg = sum(w in text for w in self.NEGATIVE_WORDS)
            sev = any(w in text for w in self.SEVERE_WORDS)
            score = float(pos - neg)
            if sev and score < 0:
                score -= 0.8
                severe += 1
            scored_items.append(
                {
                    "title": title,
                    "publisher": item.get("publisher", "Unknown"),
                    "timestamp": item.get("providerPublishTime"),
                    "score": round(score, 3),
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
        }


class TechnicalFlowAgent:
    def analyze(self, ticker: str) -> Dict[str, Any]:
        try:
            hist = yf.Ticker(ticker).history(period="6mo", interval="1d")
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
        ret = close.diff()
        up = ret.clip(lower=0).rolling(14).mean()
        down = (-ret.clip(upper=0)).rolling(14).mean()
        rs = (up / down).fillna(0)
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        avg_vol20 = float(vol.tail(20).mean()) if len(vol) >= 20 else float(vol.mean())
        vol_spike = float(vol.iloc[-1] / avg_vol20) if avg_vol20 else 1.0
        breakout = latest_close > float(close.tail(20).max() * 0.995)

        score = 0.0
        score += 0.45 if sma20 > sma50 else -0.45
        score += 0.35 if latest_close > sma20 else -0.35
        if rsi > 70:
            score -= 0.2
        elif rsi < 30:
            score += 0.2
        score += 0.25 if breakout else 0.0
        score += 0.15 if vol_spike > 1.2 else 0.0

        vote = _vote_from_score(score, threshold=0.2)
        return {
            "agent": "Technical-Flow",
            "vote": vote,
            "score": round(score, 3),
            "reason": "Trend, RSI regime, breakout context, and volume confirmation.",
            "signals": {
                "latest_close": round(latest_close, 3),
                "sma20": round(sma20, 3),
                "sma50": round(sma50, 3),
                "rsi14": round(rsi, 2),
                "volume_spike_x": round(vol_spike, 2),
                "breakout_context": breakout,
            },
        }


class RiskManagerAgent:
    def synthesize(
        self,
        ticker: str,
        current_price: float,
        horizon: str,
        agent_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        weights = {
            "Macro-Geopolitics": 0.2,
            "Commodities-FX": 0.2,
            "News-Sentiment": 0.25,
            "Technical-Flow": 0.35,
        }

        weighted = 0.0
        for result in agent_results:
            weight = weights.get(result["agent"], 0.0)
            weighted += result.get("score", 0.0) * weight

        votes = [r["vote"] for r in agent_results]
        agreement = max(votes.count("Bullish"), votes.count("Bearish"), votes.count("Neutral")) / max(len(votes), 1)
        if weighted > 0.2:
            final_call = "UP"
        elif weighted < -0.2:
            final_call = "DOWN"
        else:
            final_call = "SIDEWAYS"

        base_conf = 52 + abs(weighted) * 28 + (agreement * 14)
        if "Neutral" in votes and len(set(votes)) > 2:
            base_conf -= 8
        confidence = int(max(35, min(95, round(base_conf))))

        spread = max(0.01, min(0.04, abs(weighted) * 0.015 + 0.015))
        midpoint = current_price * (1 + (weighted * 0.02))
        lower = midpoint * (1 - spread / 2)
        upper = midpoint * (1 + spread / 2)

        invalidation = current_price * (1 - 0.012) if final_call == "UP" else current_price * (1 + 0.012)
        stop_low = current_price * (1 - 0.02)
        stop_high = current_price * (1 + 0.02)

        return {
            "agent": "Risk-Manager",
            "vote": "Risk-On" if final_call == "UP" else "Risk-Off" if final_call == "DOWN" else "Neutral",
            "weighted_score": round(weighted, 3),
            "final_call": final_call,
            "confidence": confidence,
            "time_horizon": horizon,
            "forecast": {
                "lower_bound": round(lower, 2),
                "upper_bound": round(upper, 2),
            },
            "risk_plan": {
                "invalidation_level": round(invalidation, 2),
                "stop_loss_zone": [round(stop_low, 2), round(stop_high, 2)],
                "risk_alerts": [
                    "Confidence degrades when data feeds are stale or conflicting.",
                    "Treat macro/geopolitical shocks as gap risk outside model assumptions.",
                ],
            },
        }


class CoordinatorAgent:
    def __init__(self) -> None:
        self.macro_agent = MacroGeopoliticsAgent()
        self.commodities_agent = CommoditiesFxAgent()
        self.sentiment_agent = NewsSentimentAgent()
        self.technical_agent = TechnicalFlowAgent()
        self.risk_agent = RiskManagerAgent()

    def _get_current_price(self, ticker: str) -> Tuple[float, str]:
        snap = _safe_pct_change(ticker)
        price = snap.get("last_price")
        if price is None:
            raise ValueError(f"Unable to fetch current price for {ticker}")
        return float(price), snap.get("timestamp", _utc_now_iso())

    def process_ticker(self, ticker: str, horizon: str = "1d") -> Dict[str, Any]:
        """
        Execute full multi-agent orchestration and return one fused decision object.
        """
        current_price, market_ts = self._get_current_price(ticker)

        # Use ticker-specific headlines as cross-input for macro and sentiment modules.
        sentiment_result = self.sentiment_agent.analyze(ticker)
        headlines = [h["title"] for h in sentiment_result.get("top_headlines", [])]
        macro_result = self.macro_agent.analyze(headlines)
        commodities_result = self.commodities_agent.analyze()
        technical_result = self.technical_agent.analyze(ticker)

        core_results = [macro_result, commodities_result, sentiment_result, technical_result]
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
            f"Cross-agent agreement: {len(set([r['vote'] for r in core_results])) == 1}",
        ]

        return {
            "ticker": ticker.upper(),
            "timestamp": _utc_now_iso(),
            "market_timestamp": market_ts,
            "current_price": round(current_price, 2),
            "final_call": risk_result["final_call"],
            "confidence_score": risk_result["confidence"],
            "time_horizon": risk_result["time_horizon"],
            "lower_bound": risk_result["forecast"]["lower_bound"],
            "upper_bound": risk_result["forecast"]["upper_bound"],
            "model_type": "Multi-Agent Signal Fusion v1",
            "top_drivers": top_drivers,
            "agent_votes": {
                "macro_geopolitics": {"vote": macro_result["vote"], "reason": macro_result["reason"]},
                "commodities_fx": {"vote": commodities_result["vote"], "reason": commodities_result["reason"]},
                "news_sentiment": {"vote": sentiment_result["vote"], "reason": sentiment_result["reason"]},
                "technical_flow": {"vote": technical_result["vote"], "reason": technical_result["reason"]},
                "risk_manager": {"vote": risk_result["vote"], "reason": "Weighted fusion of all agent scores."},
            },
            "risk_plan": risk_result["risk_plan"],
            "missing_data": sorted(set(missing_data)),
            "raw_agents": {
                "macro_geopolitics": macro_result,
                "commodities_fx": commodities_result,
                "news_sentiment": sentiment_result,
                "technical_flow": technical_result,
                "risk_manager": risk_result,
            },
        }

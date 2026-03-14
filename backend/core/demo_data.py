from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List


_TICKER_BASE: Dict[str, Dict[str, Any]] = {
    "RELIANCE.NS": {
        "company_name": "Reliance Industries Ltd",
        "sector": "Energy / Conglomerate",
        "current_price": 2948.7,
        "previous_close": 2921.4,
        "market_cap": "Rs 19.94T",
        "pe_ratio": 28.4,
        "div_yield": "0.34%",
        "fifty_two_week_high": 3124.8,
        "trend": "UP",
        "confidence_score": 71,
        "news": [
            {
                "title": "Reliance retail expansion and telecom resilience support market sentiment",
                "publisher": "Demo Market Wire",
                "sentiment": "POSITIVE",
            },
            {
                "title": "Energy margin outlook remains stable ahead of the next earnings cycle",
                "publisher": "Demo Business Desk",
                "sentiment": "NEUTRAL",
            },
            {
                "title": "Investors watch capex discipline and consumer growth signals",
                "publisher": "Demo Finance Network",
                "sentiment": "NEUTRAL",
            },
        ],
    },
    "TCS.NS": {
        "company_name": "Tata Consultancy Services Ltd",
        "sector": "Information Technology",
        "current_price": 4168.2,
        "previous_close": 4129.3,
        "market_cap": "Rs 15.07T",
        "pe_ratio": 31.2,
        "div_yield": "1.29%",
        "fifty_two_week_high": 4299.6,
        "trend": "UP",
        "confidence_score": 68,
        "news": [
            {
                "title": "TCS deal pipeline remains strong as enterprise AI spending improves",
                "publisher": "Demo Tech Markets",
                "sentiment": "POSITIVE",
            },
            {
                "title": "Currency volatility could affect near-term IT margin visibility",
                "publisher": "Demo Business Desk",
                "sentiment": "NEGATIVE",
            },
            {
                "title": "Analysts remain constructive on long-term digital transformation demand",
                "publisher": "Demo Finance Network",
                "sentiment": "POSITIVE",
            },
        ],
    },
    "HDFCBANK.NS": {
        "company_name": "HDFC Bank Ltd",
        "sector": "Banking",
        "current_price": 1672.5,
        "previous_close": 1661.9,
        "market_cap": "Rs 12.79T",
        "pe_ratio": 19.8,
        "div_yield": "1.15%",
        "fifty_two_week_high": 1794.2,
        "trend": "SIDEWAYS",
        "confidence_score": 63,
        "news": [
            {
                "title": "HDFC Bank asset quality remains in focus as credit growth normalizes",
                "publisher": "Demo Market Wire",
                "sentiment": "NEUTRAL",
            },
            {
                "title": "Deposit trends improve while investors track margin pressure",
                "publisher": "Demo Business Desk",
                "sentiment": "POSITIVE",
            },
            {
                "title": "Banking sector watchers expect steady but selective upside",
                "publisher": "Demo Finance Network",
                "sentiment": "NEUTRAL",
            },
        ],
    },
}


def supported_demo_tickers() -> List[str]:
    return list(_TICKER_BASE.keys())


def has_demo_data(ticker: str) -> bool:
    return ticker.upper() in _TICKER_BASE


def _generate_chart(current_price: float, trend: str, days: int = 40) -> List[Dict[str, Any]]:
    slope = {"UP": 2.4, "DOWN": -2.4, "SIDEWAYS": 0.35}.get(trend, 0.8)
    base_date = date.today() - timedelta(days=days + 10)
    start_price = current_price - (slope * days * 0.55)
    chart: List[Dict[str, Any]] = []

    for i in range(days):
        day = base_date + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        oscillation = ((i % 5) - 2) * 1.25
        open_price = start_price + slope * i + oscillation
        close_price = open_price + slope * 0.45 + (((i % 3) - 1) * 0.9)
        high_price = max(open_price, close_price) + 6.4
        low_price = min(open_price, close_price) - 6.1
        chart.append(
            {
                "time": day.isoformat(),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
            }
        )

    if chart:
        chart[-1]["close"] = round(current_price, 2)
        chart[-1]["high"] = round(max(chart[-1]["open"], current_price) + 4.2, 2)
        chart[-1]["low"] = round(min(chart[-1]["open"], current_price) - 4.1, 2)
    return chart


def get_demo_bundle(ticker: str) -> Dict[str, Any] | None:
    payload = _TICKER_BASE.get(ticker.upper())
    if not payload:
        return None

    current_price = float(payload["current_price"])
    previous_close = float(payload["previous_close"])
    chart = _generate_chart(current_price=current_price, trend=payload["trend"])
    change = round(current_price - previous_close, 2)
    change_pct = round((change / previous_close) * 100, 2) if previous_close else 0.0

    news_items = []
    for idx, item in enumerate(payload["news"]):
        news_items.append(
            {
                "title": item["title"],
                "link": "#",
                "publisher": item["publisher"],
                "sentiment": item["sentiment"],
                "timestamp": None,
                "id": idx,
            }
        )

    lower_bound = round(current_price * 0.985, 2)
    upper_bound = round(current_price * 1.018, 2)
    final_call = payload["trend"]

    return {
        "data": {
            "ticker": ticker.upper(),
            "company_name": payload["company_name"],
            "sector": payload["sector"],
            "current_price": round(current_price, 2),
            "previous_close": round(previous_close, 2),
            "regular_market_change": change,
            "regular_market_change_percent": change_pct,
            "market_cap": payload["market_cap"],
            "pe_ratio": payload["pe_ratio"],
            "div_yield": payload["div_yield"],
            "fifty_two_week_high": payload["fifty_two_week_high"],
            "data_source": "demo_fallback",
            "status_message": "Showing offline demo data because the live market provider is unavailable.",
        },
        "historical": chart,
        "news": news_items,
        "prediction": {
            "ticker": ticker.upper(),
            "timestamp": f"{date.today().isoformat()}T09:15:00+05:30",
            "market_timestamp": f"{date.today().isoformat()}T15:30:00+05:30",
            "current_price": round(current_price, 2),
            "final_call": final_call,
            "confidence_score": payload["confidence_score"],
            "time_horizon": "1d",
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "model_type": "Demo Market Signal",
            "top_drivers": [
                f"Offline demo trend profile: {final_call}",
                f"Recent price anchor around Rs {current_price:.2f}",
                "Fallback mode activated because live provider is unavailable",
            ],
            "agent_votes": {
                "macro_geopolitics": {"vote": "Neutral", "reason": "Demo fallback mode."},
                "commodities_fx": {"vote": "Neutral", "reason": "Demo fallback mode."},
                "news_sentiment": {"vote": "Neutral", "reason": "Demo fallback mode."},
                "technical_flow": {"vote": final_call, "reason": "Synthetic historical trend profile."},
                "risk_manager": {"vote": "Neutral", "reason": "Fallback demo synthesis."},
            },
            "probabilities": {
                "up": 0.52 if final_call == "UP" else 0.28,
                "down": 0.18 if final_call == "UP" else 0.24,
                "sideways": 0.30 if final_call == "UP" else 0.48,
            },
            "risk_plan": {
                "invalidation_level": round(current_price * 0.976, 2),
                "stop_loss_zone": [round(current_price * 0.97, 2), round(current_price * 1.03, 2)],
                "risk_alerts": [
                    "This is offline demo data, not a live trading signal.",
                    "Use live provider integration for production decisions.",
                ],
            },
            "missing_data": ["live_provider::unavailable"],
            "raw_agents": {},
        },
    }

from __future__ import annotations

from email.utils import parsedate_to_datetime
from typing import Any, Dict, List
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import yfinance as yf


def _normalize_news_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": (item.get("title") or "Market Update").strip(),
        "link": item.get("link", "#"),
        "publisher": item.get("publisher", "Financial Press"),
        "timestamp": item.get("providerPublishTime"),
    }


def _google_news_query(ticker: str) -> str:
    symbol = (ticker or "").upper().replace(".NS", "").replace(".BO", "")
    return f"{symbol} stock India"


def _google_news_rss(ticker: str, limit: int = 8) -> List[Dict[str, Any]]:
    query = quote_plus(_google_news_query(ticker))
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    request = Request(url, headers={"User-Agent": "AITradingEngine/1.0"})

    with urlopen(request, timeout=15) as response:
        payload = response.read()

    root = ET.fromstring(payload)
    items: List[Dict[str, Any]] = []
    for node in root.findall("./channel/item")[:limit]:
        title = (node.findtext("title") or "Market Update").strip()
        link = (node.findtext("link") or "#").strip()
        pub_date = (node.findtext("pubDate") or "").strip()
        source_node = node.find("source")
        publisher = (source_node.text or "Google News").strip() if source_node is not None else "Google News"
        timestamp = None
        if pub_date:
            try:
                timestamp = int(parsedate_to_datetime(pub_date).timestamp())
            except Exception:
                timestamp = None
        items.append(
            {
                "title": title,
                "link": link,
                "publisher": publisher,
                "timestamp": timestamp,
            }
        )
    return items


def get_live_news_headlines(ticker: str, limit: int = 8) -> List[Dict[str, Any]]:
    try:
        raw_news = yf.Ticker(ticker).news or []
        normalized = [_normalize_news_item(item) for item in raw_news[:limit]]
        if normalized:
            return normalized
    except Exception:
        pass

    try:
        return _google_news_rss(ticker, limit=limit)
    except Exception:
        return []

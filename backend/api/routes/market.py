import logging
import re
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException

from agents.coordinator_agent import CoordinatorAgent
from api import deps
from services.market_service import (
    get_search_suggestions_service,
    get_market_data_service,
    get_historical_data_service,
    get_market_news_service,
)
from services.ml_service import get_ml_prediction_service

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-=^]{1,30}$")

def _validate_ticker(ticker: str) -> str:
    ticker = (ticker or "").strip().upper()
    if not ticker or not _VALID_TICKER_RE.match(ticker):
        raise HTTPException(status_code=400, detail=f"Invalid ticker format: '{ticker}'")
    return ticker

def get_coordinator() -> CoordinatorAgent:
    return CoordinatorAgent()

@router.get("/search-suggestions", response_model=List[Dict[str, str]])
def get_search_suggestions(
    q: str,
    limit: int = 8,
    current_user=Depends(deps.get_current_user),
) -> Any:
    try:
        return get_search_suggestions_service(q, limit)
    except Exception as e:
        logger.exception("Search suggestions failed for query=%s", q)
        return []

@router.get("/data", response_model=Dict[str, Any])
def get_market_data(ticker: str, current_user=Depends(deps.get_current_user)) -> Any:
    ticker = _validate_ticker(ticker)
    try:
        return get_market_data_service(ticker)
    except Exception as e:
        logger.exception("Market data fetch failed for ticker=%s", ticker)
        raise HTTPException(status_code=500, detail=f"Market data fetch error: {str(e)}")

@router.get("/historical", response_model=List[Dict[str, Any]])
def get_historical_data(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    current_user=Depends(deps.get_current_user),
) -> Any:
    ticker = _validate_ticker(ticker)
    try:
        return get_historical_data_service(ticker, period, interval)
    except Exception:
        logger.exception("Historical data fetch failed for ticker=%s", ticker)
        return []

@router.get("/news", response_model=List[Dict[str, Any]])
def get_market_news(ticker: str, current_user=Depends(deps.get_current_user)) -> Any:
    ticker = _validate_ticker(ticker)
    try:
        return get_market_news_service(ticker)
    except Exception:
        logger.exception("News fetch failed for ticker=%s", ticker)
        return []

@router.get("/prediction", response_model=Dict[str, Any])
async def get_prediction_bounds(
    ticker: str,
    current_price: float | None = None,
    sentiment: str = "NEUTRAL",
    horizon: str = "1d",
    current_user=Depends(deps.get_current_user),
    coordinator: CoordinatorAgent = Depends(get_coordinator),
) -> Any:
    """
    Real-time multi-agent prediction endpoint.
    Kept backward compatible with legacy query params.
    """
    ticker = _validate_ticker(ticker)
    try:
        return await coordinator.process_ticker(ticker=ticker, horizon=horizon, current_price=current_price)
    except Exception as e:
        logger.exception("Multi-agent prediction error for ticker=%s", ticker)
        raise HTTPException(status_code=500, detail=f"Multi-agent prediction error: {str(e)}")


@router.get("/realtime-analysis", response_model=Dict[str, Any])
async def get_realtime_analysis(
    ticker: str,
    horizon: str = "1d",
    current_user=Depends(deps.get_current_user),
    coordinator: CoordinatorAgent = Depends(get_coordinator),
) -> Any:
    """
    Explicit real-time analysis route returning full multi-agent output.
    """
    ticker = _validate_ticker(ticker)
    try:
        return await coordinator.process_ticker(ticker=ticker, horizon=horizon)
    except Exception as e:
        logger.exception("Realtime analysis error for ticker=%s", ticker)
        raise HTTPException(status_code=500, detail=f"Realtime analysis error: {str(e)}")

@router.get("/ml-prediction", response_model=Dict[str, Any])
def get_ml_prediction(
    ticker: str,
    model_type: str = "random_forest",
    horizon: int = 1,
    current_user=Depends(deps.get_current_user)
) -> Any:
    """
    Query the actual locally trained ML models from the src pipeline.
    Requires models to have been built via CLI first.
    """
    ticker = _validate_ticker(ticker)
    result = get_ml_prediction_service(ticker=ticker, model_type=model_type, horizon=horizon)
    if result.get("status") in ["error", "not_trained"]:
        status_code = 404 if result["status"] == "not_trained" else 500
        raise HTTPException(status_code=status_code, detail=result.get("message"))
    return result

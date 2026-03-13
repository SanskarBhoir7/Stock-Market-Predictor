from fastapi import APIRouter, HTTPException, Depends
from typing import Any, Dict, List
import yfinance as yf
from api import deps
import pandas as pd
from core.ml_gan import GANForecaster

router = APIRouter()

@router.get("/data", response_model=Dict[str, Any])
def get_market_data(ticker: str, current_user = Depends(deps.get_current_user)) -> Any:
    """
    Fetch live market data (financials, OHLC, market cap) from Yahoo Finance.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            hist = stock.history(period="1d")
            if hist.empty:
                raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
            
            current_price = hist['Close'].iloc[-1]
            return {
                "ticker": ticker.upper(),
                "current_price": round(current_price, 2),
                "company_name": ticker,
                "sector": "Unknown",
                "market_cap": "N/A",
                "pe_ratio": "N/A",
                "div_yield": "N/A",
                "fifty_two_week_high": "N/A",
                "regular_market_change": 0.0,
                "regular_market_change_percent": 0.0
            }
        
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        previous_close = info.get('previousClose', current_price)
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100 if previous_close else 0

        mCap = info.get('marketCap')
        if mCap:
            if mCap > 1_000_000_000_000:
                mCap_formatted = f"₹{mCap / 1_000_000_000_000:.2f}T"
            elif mCap > 1_000_000_000:
                mCap_formatted = f"₹{mCap / 1_000_000_000:.2f}B"
            else:
                mCap_formatted = f"₹{mCap}"
        else:
            mCap_formatted = "N/A"

        return {
            "ticker": ticker.upper(),
            "company_name": info.get('shortName', ticker),
            "sector": info.get('sector', 'Multi-Sector'),
            "current_price": round(current_price, 2),
            "previous_close": round(previous_close, 2),
            "regular_market_change": round(change, 2),
            "regular_market_change_percent": round(change_percent, 2),
            "market_cap": mCap_formatted,
            "pe_ratio": info.get('trailingPE', 'N/A'),
            "div_yield": f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else "N/A",
            "fifty_two_week_high": round(info.get('fiftyTwoWeekHigh', 0), 2)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Market data fetch error: {str(e)}")

@router.get("/historical", response_model=List[Dict[str, Any]])
def get_historical_data(ticker: str, period: str = "6mo", current_user = Depends(deps.get_current_user)) -> Any:
    """
    Fetch historical OHLCV data for Drawing the Japanese Candlestick charts on the UI.
    periods: 1mo, 3mo, 6mo, 1y, 2y, 5y
    """
    try:
        stock = yf.Ticker(ticker)
        # Fetch data up to the desired period
        hist = stock.history(period=period)
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No historical data found for {ticker}")

        # Lightweight charts expects specific {time: 'YYYY-MM-DD', open, high, low, close} structure format
        chart_data = []
        for date_obj, row in hist.iterrows():
            # Extract date string correctly from pandas Timestamp index
            date_str = date_obj.strftime('%Y-%m-%d')
            chart_data.append({
                "time": date_str,
                "open": round(row['Open'], 2),
                "high": round(row['High'], 2),
                "low": round(row['Low'], 2),
                "close": round(row['Close'], 2),
            })
            
        return chart_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Market history fetch error: {str(e)}")

@router.get("/news", response_model=List[Dict[str, Any]])
def get_market_news(ticker: str, current_user = Depends(deps.get_current_user)) -> Any:
    """
    Simulated sentiment analyzer agent data fetching Yahoo Finance direct headlines.
    """
    try:
        stock = yf.Ticker(ticker)
        raw_news = stock.news
        formatted_news = []
        
        # Parse top 3-4 news items
        for n in raw_news[:4]:
            # Mocking a sentient 'SentimentAgent' analysis result for UI 
            title = n.get('title', 'Market Update')
            
            # Very basic mock logic for sentiment scoring just to look beautiful
            sentiment_tag = "NEUTRAL"
            if any(word in title.upper() for word in ['UP', 'JUMP', 'SOAR', 'GAIN', 'PROFIT', 'GROWTH', 'BUY']):
                sentiment_tag = "POSITIVE"
            elif any(word in title.upper() for word in ['DOWN', 'FALL', 'PLUNGE', 'LOSS', 'DEBT', 'CRASH', 'SELL']):
                sentiment_tag = "NEGATIVE"
                
            formatted_news.append({
                "title": title,
                "link": n.get('link', '#'),
                "publisher": n.get('publisher', 'Financial Press'),
                "sentiment": sentiment_tag,
                "timestamp": n.get('providerPublishTime')
            })
            
        return formatted_news
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"News sentiment fetch error: {str(e)}")

@router.get("/prediction", response_model=Dict[str, Any])
def get_prediction_bounds(ticker: str, current_price: float, sentiment: str = "NEUTRAL", current_user = Depends(deps.get_current_user)) -> Any:
    """
    Interfaces with the TimeGAN Simulator to output confidence intervals.
    """
    try:
        stock = yf.Ticker(ticker)
        # Gather 3 months of volatility
        hist = stock.history(period="3mo")
        ohlcv = []
        if not hist.empty:
            for _, row in hist.iterrows():
                ohlcv.append({"close": row['Close'] })
        
        forecaster = GANForecaster(ticker)
        bounds = forecaster.generate_confidence_bounds(current_price, ohlcv, sentiment)
        
        return bounds
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GAN ML generator error: {str(e)}")

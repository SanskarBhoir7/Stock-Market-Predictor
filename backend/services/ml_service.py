import sys
import os
import logging
from typing import Dict, Any

# Ensure we can import from the sibling `src` directory containing the ML pipeline
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from src.predictor import predict_next_close
    _ML_AVAILABLE = True
except ImportError:
    _ML_AVAILABLE = False


logger = logging.getLogger(__name__)

def get_ml_prediction_service(ticker: str, model_type: str = "random_forest", horizon: int = 1) -> Dict[str, Any]:
    """
    Service wrapper for the ML pipeline's `predict_next_close` function.
    Provides graceful degradation if the model file is not found.
    """
    if not _ML_AVAILABLE:
        return {
            "status": "error",
            "message": "ML pipeline source code could not be loaded."
        }
        
    try:
        predicted_price = predict_next_close(ticker=ticker, model_type=model_type, horizon=horizon)
        return {
            "status": "success",
            "ticker": ticker.upper(),
            "model_type": model_type,
            "horizon_days": horizon,
            "predicted_close": round(predicted_price, 2)
        }
    except FileNotFoundError:
        return {
            "status": "not_trained",
            "message": f"No trained {model_type} model found for {ticker} at {horizon}d horizon. Train it first via CLI."
        }
    except Exception as e:
        logger.exception("ML prediction failed for ticker=%s", ticker)
        return {
            "status": "error",
            "message": f"ML pipeline error: {str(e)}"
        }

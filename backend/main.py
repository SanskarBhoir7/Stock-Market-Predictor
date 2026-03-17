from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from threading import Thread

from core.config import settings
from core.upstox_data import has_upstox_config, warm_instrument_cache
from database import engine, Base
import models.user  # import models here to ensure they are registered with Base

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API combining real-time market data and multi-agent market analysis.",
)

app.state.db_ready = False
app.state.db_error = None
app.state.upstox_cache_ready = False


def initialize_database() -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        Base.metadata.create_all(bind=engine)
        app.state.db_ready = True
        app.state.db_error = None
    except SQLAlchemyError as exc:
        app.state.db_ready = False
        app.state.db_error = str(exc)

# Allow React Frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup() -> None:
    initialize_database()
    if has_upstox_config():
        def _warm_upstox() -> None:
            try:
                warm_instrument_cache()
                app.state.upstox_cache_ready = True
            except Exception:
                app.state.upstox_cache_ready = False

        Thread(target=_warm_upstox, daemon=True).start()


@app.get("/")
def read_root():
    return {
        "message": "AI Trading Platform Backend is Running!",
        "version": settings.VERSION,
        "database_ready": app.state.db_ready,
        "agents": [
            "MacroGeopoliticsAgent",
            "CommoditiesFxAgent",
            "NewsSentimentAgent",
            "TechnicalFlowAgent",
            "RiskManagerAgent"
        ]
    }


@app.get("/health")
def health_check():
    if has_upstox_config():
        provider_status = "connected" if app.state.upstox_cache_ready else "connecting"
    else:
        provider_status = "not_configured"
    return {
        "status": "ok",
        "environment": settings.APP_ENV,
        "database_ready": app.state.db_ready,
        "database_error": app.state.db_error,
        "market_provider": "upstox" if has_upstox_config() else "fallback_only",
        "market_provider_status": provider_status,
    }

from api.routes import api_router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

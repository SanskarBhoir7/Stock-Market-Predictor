import logging
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from core.upstox_data import has_upstox_config, warm_instrument_cache
from database import engine, Base
import models.user  # import models here to ensure they are registered with Base

logger = logging.getLogger(__name__)


def initialize_database():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully.")
        return True, None
    except SQLAlchemyError as exc:
        logger.error("Database initialization failed: %s", exc)
        return False, str(exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan handler — replaces deprecated @app.on_event('startup')."""
    settings.validate_secret_key()

    db_ready, db_error = initialize_database()
    app.state.db_ready = db_ready
    app.state.db_error = db_error
    app.state.upstox_cache_ready = False

    if has_upstox_config():
        def _warm_upstox() -> None:
            try:
                warm_instrument_cache()
                app.state.upstox_cache_ready = True
                logger.info("Upstox instrument cache warmed successfully.")
            except Exception:
                app.state.upstox_cache_ready = False
                logger.warning("Upstox instrument cache warm-up failed.")

        Thread(target=_warm_upstox, daemon=True).start()

    yield  # Application runs here


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API combining real-time market data and multi-agent market analysis.",
    lifespan=lifespan,
)

# Allow React Frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "message": "AI Trading Platform Backend is Running!",
        "version": settings.VERSION,
        "database_ready": getattr(app.state, "db_ready", False),
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
        provider_status = "connected" if getattr(app.state, "upstox_cache_ready", False) else "connecting"
    else:
        provider_status = "not_configured"
    return {
        "status": "ok",
        "environment": settings.APP_ENV,
        "database_ready": getattr(app.state, "db_ready", False),
        "database_error": getattr(app.state, "db_error", None),
        "market_provider": "upstox" if has_upstox_config() else "fallback_only",
        "market_provider_status": provider_status,
    }


from api.routes import api_router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

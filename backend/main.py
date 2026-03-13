from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from database import engine, Base
import models.user  # import models here to ensure they are registered with Base

# Create tables in MySQL if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API combining real-time market data, GAN forecasting, and Multi-Agent Orchestration.",
)

# Allow React Frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "message": "AI Trading Platform Backend is Running!",
        "version": settings.VERSION,
        "agents": [
            "DataGathererAgent",
            "SentimentAgent",
            "PredictionAgent",
            "ReportingAgent"
        ]
    }

from api.routes import api_router
app.include_router(api_router, prefix="/api/v1")

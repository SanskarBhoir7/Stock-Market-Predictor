from fastapi import APIRouter
from api.routes import auth, market

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
# api_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])

"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.conversation import router as conversation_router
from app.api.v1.transactions import router as transactions_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(conversation_router, prefix="/conversation", tags=["conversation"])
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])
api_router.include_router(transactions_router, prefix="/transactions", tags=["transactions"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])

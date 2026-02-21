"""API v1 router configuration.

This module sets up the main API router and includes all sub-routers for different
endpoints like authentication and chatbot functionality.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.conversation import router as conversation_router

api_router = APIRouter()

# Include routers
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(conversation_router, prefix="/conversation", tags=["conversation"])
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])

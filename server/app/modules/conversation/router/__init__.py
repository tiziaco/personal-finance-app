"""The conversation routes: CRUD under /conversation, chat under /chatbot."""

from fastapi import APIRouter

from app.modules.conversation.router.chatbot import router as chatbot_router
from app.modules.conversation.router.conversation import router as conversation_router

router = APIRouter()
router.include_router(conversation_router)
router.include_router(chatbot_router)

"""API v1 router — includes each module's router. Prefixes and tags live in the modules."""

from fastapi import APIRouter

from app.modules import account, conversation, transaction

api_router = APIRouter()
api_router.include_router(account.router)
api_router.include_router(conversation.router)
api_router.include_router(transaction.imports_router)
api_router.include_router(transaction.router)

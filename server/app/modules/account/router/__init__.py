"""The account routes: the profile under /auth, the Clerk receiver under /webhooks."""

from fastapi import APIRouter

from app.modules.account.router.auth import router as auth_router
from app.modules.account.router.webhooks import router as webhooks_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(webhooks_router)

"""Clerk webhook endpoint.

Deliberately carries no rate limit. svix bursts on retry, and a 429 reads as
a failed delivery, provoking further retries. The signature check is the gate
and it is cheap.

No user identity reaches this route: there is no bearer token. If row-level
security is ever added, this path writes as Clerk's events dictate, not on
behalf of a signed-in user, and will need a service-role escape hatch.
"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
)

from app.database.dependencies import DbSession
from app.integrations.clerk.webhooks import (
    VerifiedEvent,
    WebhookContext,
    verify_clerk_webhook,
)
from app.modules.account.webhooks import clerk_dispatcher

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/clerk",
    status_code=204,
    operation_id="clerkWebhook",
    summary="Clerk webhook receiver",
    include_in_schema=False,
)
async def clerk_webhook(
    verified: Annotated[VerifiedEvent, Depends(verify_clerk_webhook)],
    session: DbSession,
) -> None:
    """Receive a verified Clerk webhook event and dispatch it.

    Args:
        verified: The verified event and its svix delivery id, produced by
            the signature dependency.
        session: Database session.
    """
    await clerk_dispatcher.dispatch(
        WebhookContext(
            event=verified.event,
            message_id=verified.message_id,
            session=session,
        )
    )

"""Clerk webhook ingestion — verify, parse, dispatch.

The whole inbound path reads in order from this package: `verification`
authenticates the request and decodes the envelope, `schemas` defines what it
produces; `dispatcher` routing and the handlers live in the module that owns
the rows — `app.modules.account.webhooks`.
"""

from app.integrations.clerk.webhooks.exceptions import (
    InvalidWebhookSignatureError,
    WebhookError,
    WebhookPayloadTooLargeError,
)
from app.integrations.clerk.webhooks.schemas import (
    ClerkEvent,
    VerifiedEvent,
    WebhookContext,
)
from app.integrations.clerk.webhooks.verification import verify_clerk_webhook

__all__ = [
    "ClerkEvent",
    "VerifiedEvent",
    "WebhookContext",
    "InvalidWebhookSignatureError",
    "WebhookError",
    "WebhookPayloadTooLargeError",
    "verify_clerk_webhook",
]

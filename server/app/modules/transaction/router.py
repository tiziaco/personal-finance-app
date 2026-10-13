"""Transaction routes under /transactions. Named paths are declared before /{transaction_id}."""

from typing import List

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.limiter import limiter
from app.modules.account import CurrentUser
from app.modules.transaction.schemas import CategoryResponse
from app.modules.transaction.service import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get(
    "/categories",
    operation_id="listTransactionCategories",
    response_model=List[CategoryResponse],
    summary="List the categories",
    description="Every category a transaction can carry, in display order.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])
async def list_categories(request: Request, user: CurrentUser) -> List[CategoryResponse]:
    """The category list; the web's only source of category labels."""
    return transaction_service.list_categories()

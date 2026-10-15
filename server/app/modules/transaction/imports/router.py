"""Import routes under /transactions/imports, tag "transaction-imports"."""

from fastapi import APIRouter, File, Request, UploadFile

from app.core.config import settings
from app.core.limiter import limiter, user_or_ip_key
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.transaction.imports.domain import MAX_BYTES
from app.modules.transaction.imports.schemas import ImportPreview
from app.modules.transaction.imports.service import import_service

router = APIRouter(prefix="/transactions/imports", tags=["transaction-imports"])


@router.post(
    "",
    operation_id="uploadTransactionsCsv",
    response_model=ImportPreview,
    status_code=201,
    summary="Upload a CSV",
    description="Hold a bank's CSV export for 30 minutes and propose which column is which. A file this app "
    "cannot read is 422 INVALID_IMPORT_FILE, with details.reason. A new upload replaces the one held before.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTION_IMPORTS[0], key_func=user_or_ip_key)
async def upload_transactions_csv(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    file: UploadFile = File(..., description="The bank's CSV export, at most 5 MB"),
) -> ImportPreview:
    """Upload a CSV and get its proposed mapping."""
    raw = await file.read(MAX_BYTES + 1)  # one byte over is enough to refuse it
    return await import_service.upload(db_session, user.id, file.filename or "", raw)

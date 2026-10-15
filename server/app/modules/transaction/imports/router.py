"""Import routes under /transactions/imports, tag "transaction-imports"."""

import uuid

from fastapi import APIRouter, File, Request, UploadFile

from app.core.config import settings
from app.core.limiter import limiter, user_or_ip_key
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.transaction.imports.domain import MAX_BYTES
from app.modules.transaction.imports.schemas import ImportConfirm, ImportPreview, ImportResult
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


@router.post(
    "/{upload_id}/confirm",
    operation_id="confirmTransactionsImport",
    response_model=ImportResult,
    summary="Confirm an import",
    description="Read the held file through the confirmed mapping, skip duplicates, categorise every row and save. "
    "404 IMPORT_UPLOAD_NOT_FOUND for an expired, confirmed, replaced or another user's upload; 422 "
    "INVALID_IMPORT_MAPPING with details.reason; 503 CATEGORISATION_UNAVAILABLE keeps the upload for a retry.",
)
@limiter.shared_limit(
    settings.rate_limits.endpoints.TRANSACTION_IMPORTS[0], scope="transaction-imports-confirm", key_func=user_or_ip_key
)
async def confirm_transactions_import(
    request: Request, upload_id: uuid.UUID, body: ImportConfirm, db_session: DbSession, user: CurrentUser
) -> ImportResult:
    """Confirm a held upload's mapping and import it."""
    mapping = {column: field.value for column, field in body.mapping.items()}
    return await import_service.confirm(db_session, user.id, upload_id, mapping)

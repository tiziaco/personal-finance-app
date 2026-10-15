"""The import: upload a bank's CSV, review its mapping, confirm (docs/product/features/csv-import.md)."""

import statistics
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.csv_mapping import ColumnHint, propose_mapping
from app.agents.transaction_labeler import MerchantToLabel, label
from app.core.logging import logger
from app.modules.transaction.domain import fingerprint, normalise_merchant, plan_count_matched
from app.modules.transaction.imports.domain import (
    MAX_BYTES,
    ColumnProfile,
    CsvFormatError,
    CsvRow,
    ImportField,
    ImportRow,
    ParsedCsv,
    clean_proposal,
    column_key,
    decode,
    mapping_problem,
    parse,
    pick_samples,
    profile_columns,
    read_rows,
)
from app.modules.transaction.imports.exceptions import (
    CategorisationUnavailableError,
    ImportUploadNotFoundError,
    InvalidImportFileError,
    InvalidImportMappingError,
)
from app.modules.transaction.imports.repository import import_repository
from app.modules.transaction.imports.schemas import (
    ImportColumn,
    ImportPreview,
    ImportRejection,
    ImportResult,
    MappingSource,
)
from app.modules.transaction.schemas import CATEGORIES, TransactionImport
from app.modules.transaction.service import transaction_service

UPLOAD_TTL = timedelta(minutes=30)


async def _release_connection(session: AsyncSession) -> None:
    """Commit what the request has done so far, handing the connection back before a model call.

    The import's model calls take seconds, and DbSession would otherwise hold its
    pool connection idle in a transaction through them (docs/TODO.md, "a model
    call holds the request's DB connection"). Nothing written before this point
    depends on what follows: at most a held upload, which must survive a failed
    model call anyway. The session opens a new transaction on its next use, and
    DbSession commits that one after the route as usual. The only commits outside
    DbSession in this app; keep it that way.
    """
    await session.commit()


def _merchants_to_label(rows: list[ImportRow]) -> list[MerchantToLabel]:
    """One item per merchant key: its first spelling, a description and bank category if any row has one, the median amount."""
    by_key: dict[str, list[ImportRow]] = {}
    for row in rows:
        by_key.setdefault(normalise_merchant(row.merchant), []).append(row)
    return [
        MerchantToLabel(
            key=key,
            merchant=group[0].merchant,
            description=next((r.description for r in group if r.description), None),
            original_category=next((r.original_category for r in group if r.original_category), None),
            amount=statistics.median_low([r.amount for r in group]),
        )
        for key, group in by_key.items()
    ]


class ImportService:
    """Orchestrates the import."""

    @staticmethod
    async def upload(session: AsyncSession, user_id: uuid.UUID, filename: str, raw: bytes) -> ImportPreview:
        """Read a file, hold it for 30 minutes, and propose a mapping. Raises InvalidImportFileError."""
        if not filename.casefold().endswith(".csv"):
            raise InvalidImportFileError("Only .csv files can be imported", reason="not_csv")
        if len(raw) > MAX_BYTES:
            raise InvalidImportFileError("The file is larger than 5 MB", reason="too_large")
        text = decode(raw)
        try:
            parsed = parse(text)
        except CsvFormatError as e:
            raise InvalidImportFileError(e.message, reason=e.reason) from e
        held = await import_repository.replace_upload(session, user_id, text, datetime.now(UTC) + UPLOAD_TTL)
        profiles = profile_columns(parsed)
        samples = pick_samples(parsed)
        mapping, source = await ImportService._propose(session, user_id, held.id, parsed, profiles, samples)
        logger.info("csv_upload_previewed", user_id=user_id, rows=len(parsed.rows), mapping_source=source.value)
        return ImportPreview(
            upload_id=held.id,
            filename=filename,
            row_count=len(parsed.rows),
            mapping_source=source,
            columns=[
                ImportColumn(
                    name=p.name,
                    proposed_field=mapping[p.name],
                    empty_rate=p.empty_rate,
                    date_format=p.date_format,
                    amount_style=p.amount_style,
                )
                for p in profiles
            ],
            sample_rows=[row.cells for row in samples],
        )

    @staticmethod
    async def _propose(
        session: AsyncSession,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
        parsed: ParsedCsv,
        profiles: list[ColumnProfile],
        samples: list[CsvRow],
    ) -> tuple[dict[str, ImportField], MappingSource]:
        """The remembered mapping for these columns, else the agent's, else every column ignored."""
        remembered = await import_repository.get_profile(session, user_id, column_key(parsed.columns))
        if remembered is not None:
            # The profile is keyed by names folded; the new file may differ in case or spacing.
            folded = {name.strip().casefold(): field for name, field in remembered.mapping.items()}
            mapping = {c: folded.get(c.strip().casefold(), ImportField.IGNORE) for c in parsed.columns}
            return clean_proposal(parsed.columns, mapping), MappingSource.REMEMBERED
        await _release_connection(session)
        proposal = await propose_mapping(
            [ColumnHint(p.name, p.empty_rate, p.date_format, p.amount_style) for p in profiles],
            [row.cells for row in samples],
            user_id=user_id,
            upload_id=upload_id,
        )
        if proposal is None:
            return {c: ImportField.IGNORE for c in parsed.columns}, MappingSource.NONE
        return clean_proposal(parsed.columns, proposal), MappingSource.PROPOSED

    @staticmethod
    async def confirm(
        session: AsyncSession, user_id: uuid.UUID, upload_id: uuid.UUID, mapping: dict[str, ImportField]
    ) -> ImportResult:
        """Read the held file through the mapping, skip duplicates, label, save (spec §5.3).

        Raises ImportUploadNotFoundError, InvalidImportMappingError, or
        CategorisationUnavailableError — after which nothing is saved and the
        upload is still held.
        """
        held = await import_repository.get_live_upload(session, user_id, upload_id, datetime.now(UTC))
        if held is None:
            raise ImportUploadNotFoundError("Upload not found or expired", upload_id=str(upload_id))
        parsed = parse(held.content)
        problem = mapping_problem(parsed.columns, mapping)
        if problem is not None:
            raise InvalidImportMappingError(problem.message, reason=problem.reason)
        rows, rejected = read_rows(parsed, mapping)

        prints = [fingerprint(user_id, r.date, r.merchant, r.amount, r.description) for r in rows]
        existing = await transaction_service.count_active_by_fingerprints(session, user_id, prints)
        fresh = [row for row, keep in zip(rows, plan_count_matched(prints, existing), strict=True) if keep]

        await _release_connection(session)
        labelled = await label(_merchants_to_label(fresh), CATEGORIES, user_id=user_id, upload_id=upload_id)
        if labelled.all_failed:
            raise CategorisationUnavailableError("Categorisation is unavailable", upload_id=str(upload_id))

        if not await import_repository.take_upload(session, user_id, upload_id):
            raise ImportUploadNotFoundError("Upload not found", upload_id=str(upload_id))
        keys = [normalise_merchant(row.merchant) for row in fresh]
        imported = await transaction_service.import_many(
            session,
            user_id,
            [
                TransactionImport(
                    date=row.date,
                    merchant=row.merchant,
                    amount=row.amount,
                    description=row.description,
                    original_category=row.original_category,
                    category=labelled.labels[key].category,
                    confidence=labelled.labels[key].confidence,
                    is_recurring=row.is_recurring,
                )
                for row, key in zip(fresh, keys, strict=True)
            ],
        )
        await import_repository.put_profile(session, user_id, column_key(parsed.columns), mapping)
        result = ImportResult(
            imported=imported,
            skipped_duplicates=len(rows) - len(fresh),
            uncategorised=sum(key in labelled.fallback_keys for key in keys),
            rejected=[ImportRejection(row=r.number, reason=r.reason) for r in rejected],
        )
        logger.info(
            "transactions_imported",
            user_id=user_id,
            imported=result.imported,
            skipped=result.skipped_duplicates,
            uncategorised=result.uncategorised,
            rejected=len(result.rejected),
        )
        return result

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Erasure: the user's remembered mappings and held upload."""
        await import_repository.delete_all_for_user(session, user_id)


import_service = ImportService()

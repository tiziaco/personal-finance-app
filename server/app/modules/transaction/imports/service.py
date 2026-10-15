"""The import: upload a bank's CSV, review its mapping, confirm (docs/product/features/csv-import.md)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.csv_mapping import ColumnHint, propose_mapping
from app.core.logging import logger
from app.modules.transaction.imports.domain import (
    IGNORE,
    MAX_BYTES,
    ColumnProfile,
    CsvFormatError,
    CsvRow,
    ParsedCsv,
    clean_proposal,
    column_key,
    decode,
    parse,
    pick_samples,
    profile_columns,
)
from app.modules.transaction.imports.exceptions import InvalidImportFileError
from app.modules.transaction.imports.repository import import_repository
from app.modules.transaction.imports.schemas import ImportColumn, ImportPreview, MappingSource

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
    ) -> tuple[dict[str, str], MappingSource]:
        """The remembered mapping for these columns, else the agent's, else every column ignored."""
        remembered = await import_repository.get_profile(session, user_id, column_key(parsed.columns))
        if remembered is not None:
            # The profile is keyed by names folded; the new file may differ in case or spacing.
            folded = {name.strip().casefold(): field for name, field in remembered.mapping.items()}
            mapping = {c: folded.get(c.strip().casefold(), IGNORE) for c in parsed.columns}
            return clean_proposal(parsed.columns, mapping), MappingSource.REMEMBERED
        await _release_connection(session)
        proposal = await propose_mapping(
            [ColumnHint(p.name, p.empty_rate, p.date_format, p.amount_style) for p in profiles],
            [row.cells for row in samples],
            user_id=user_id,
            upload_id=upload_id,
        )
        if proposal is None:
            return {c: IGNORE for c in parsed.columns}, MappingSource.NONE
        return clean_proposal(parsed.columns, proposal), MappingSource.PROPOSED

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Erasure: the user's remembered mappings and held upload."""
        await import_repository.delete_all_for_user(session, user_id)


import_service = ImportService()

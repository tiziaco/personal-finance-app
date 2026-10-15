"""The import's request and response schemas."""

import uuid
from enum import StrEnum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.modules.transaction.imports.domain import ImportField


class MappingSource(StrEnum):
    """Where a preview's mapping came from."""

    REMEMBERED = "remembered"
    PROPOSED = "proposed"
    NONE = "none"


class ImportColumn(BaseModel):
    """One column of an uploaded file, as the review shows it."""

    name: str = Field(..., description="The column's name in the file's header")
    proposed_field: ImportField = Field(..., description="The field the app proposes for it")
    empty_rate: float = Field(..., description="The share of rows where it is empty, 0 to 1")
    date_format: Optional[str] = Field(None, description="The date format detected in it, such as dd.mm.yyyy")
    amount_style: Optional[str] = Field(None, description="The amount style detected in it: 1.234,56 or 1,234.56")


class ImportPreview(BaseModel):
    """An uploaded file held for 30 minutes, and its proposed mapping."""

    upload_id: uuid.UUID = Field(..., description="The held upload; confirm takes it")
    filename: str = Field(..., description="The uploaded file's name")
    row_count: int = Field(..., description="Data rows in the file")
    mapping_source: MappingSource = Field(..., description="remembered, proposed by AI, or none")
    columns: List[ImportColumn] = Field(..., description="Every column, in file order")
    sample_rows: List[List[str]] = Field(..., description="Up to three rows, cells in column order")


class ImportConfirm(BaseModel):
    """The mapping the user confirmed. A column left out is ignored."""

    mapping: Dict[str, ImportField] = Field(..., description="Column name to field")


class ImportRejection(BaseModel):
    """A row that was not imported."""

    row: int = Field(..., description="The row's line number in the file")
    reason: str = Field(..., description="Why it was left out")


class ImportResult(BaseModel):
    """What a confirm did."""

    imported: int = Field(..., description="Rows saved")
    skipped_duplicates: int = Field(..., description="Rows already held, skipped")
    uncategorised: int = Field(
        ..., description="Rows saved under Miscellaneous because the labeller could not place them"
    )
    rejected: List[ImportRejection] = Field(..., description="Rows left out, in file order")

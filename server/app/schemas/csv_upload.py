"""Schemas for the two-step CSV transaction upload flow."""

from typing import Any, Dict, List, Optional

from sqlmodel import SQLModel


class CSVUploadProposalResponse(SQLModel):
    """Response from POST /transactions/upload (step 1).

    Returns the proposed column→field mapping and sample rows for the user
    to verify before confirming the import.
    """

    mapping_id: str
    proposed_mapping: Dict[str, str]  # {"Buchungsdatum": "date", "Betrag": "amount", ...}
    sample_rows: List[Dict[str, Any]]  # first 3 parsed rows for visual verification


class CSVConfirmRequest(SQLModel):
    """Request body for POST /transactions/upload/{mapping_id}/confirm (step 2).

    The client sends back the (possibly corrected) mapping.
    """

    confirmed_mapping: Dict[str, str]  # same shape as proposed_mapping


class CSVUploadResponse(SQLModel):
    """Response from POST /transactions/upload/{mapping_id}/confirm (step 2)."""

    imported: int
    skipped: int
    errors: List[str]

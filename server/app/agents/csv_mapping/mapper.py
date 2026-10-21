"""The column-mapping agent: proposes which CSV column is which field (docs/product/features/csv-import.md §3)."""

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import RootModel

from app.agents.core import create_trace_config
from app.agents.shared.structured import ask_json, structured_llm_service
from app.core.logging import logger

CELL_LIMIT = 100
_PROMPT = (Path(__file__).parent / "prompts" / "v1.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class ColumnHint:
    """What the model is told about a column besides its samples."""

    name: str
    empty_rate: float
    date_format: Optional[str]
    amount_style: Optional[str]


class _Mapping(RootModel[dict[str, str]]):
    pass


async def propose_mapping(
    columns: list[ColumnHint], samples: list[list[str]], *, user_id: uuid.UUID, upload_id: uuid.UUID
) -> Optional[dict[str, str]]:
    """The model's {column: field}, checked for shape only, or None when the call fails for any reason."""
    payload = {
        "columns": [
            {
                "name": c.name,
                "empty_rate": round(c.empty_rate, 2),
                "date_format": c.date_format,
                "amount_style": c.amount_style,
            }
            for c in columns
        ],
        "sample_rows": [[cell[:CELL_LIMIT] for cell in row] for row in samples],
    }
    try:
        answer = await ask_json(
            structured_llm_service,
            _PROMPT,
            json.dumps(payload, ensure_ascii=False),
            _Mapping,
            create_trace_config(user_id, upload_id, "csv_mapping"),
        )
    except Exception as e:  # noqa: BLE001  the review then asks the user to map by hand; an upload never fails on this
        logger.warning("csv_mapping_failed", error_type=type(e).__name__)
        return None
    return answer.root

"""The column-mapping agent (spec §6.2). The model is stubbed."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from uuid_utils.compat import uuid7

from app.agents.csv_mapping import CELL_LIMIT, ColumnHint, propose_mapping
from app.integrations.llm import LLMAPIError

pytestmark = pytest.mark.unit

IDS = {"user_id": uuid7(), "upload_id": uuid7()}
COLUMNS = [ColumnHint("Buchungsdatum", 0.0, "dd.mm.yyyy", None), ColumnHint("Betrag", 0.0, None, "1.234,56")]


@pytest.fixture(autouse=True)
def no_langfuse():
    with patch("app.agents.csv_mapping.mapper.create_trace_config", return_value={}):
        yield


async def test_returns_the_models_mapping_and_sends_hints_and_capped_samples():
    seen = {}

    async def fake(shape, system, user, config):
        seen.update(json.loads(user))
        return shape.model_validate({"Buchungsdatum": "date", "Betrag": "amount"})

    with patch("app.agents.csv_mapping.mapper.ask", fake):
        mapping = await propose_mapping(COLUMNS, [["15.01.2026", "x" * 500]], **IDS)
    assert mapping == {"Buchungsdatum": "date", "Betrag": "amount"}
    assert seen["columns"][0] == {
        "name": "Buchungsdatum",
        "empty_rate": 0.0,
        "date_format": "dd.mm.yyyy",
        "amount_style": None,
    }
    assert len(seen["sample_rows"][0][1]) == CELL_LIMIT


@pytest.mark.parametrize("error", [LLMAPIError("down"), ValueError("bad json"), RuntimeError("no key")])
async def test_any_failure_is_none(error):
    with patch("app.agents.csv_mapping.mapper.ask", AsyncMock(side_effect=error)):
        assert await propose_mapping(COLUMNS, [], **IDS) is None

"""The labeller: known merchants, batches, fallbacks (spec §6.3). The model is stubbed."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from uuid_utils.compat import uuid7

from app.agents.shared.structured import InvalidModelAnswer
from app.agents.transaction_labeler import (
    BATCH_SIZE,
    FALLBACK_CATEGORY,
    FALLBACK_CONFIDENCE,
    KNOWN_CONFIDENCE,
    Label,
    MerchantToLabel,
    label,
)
from app.integrations.llm import LLMAPIError

pytestmark = pytest.mark.unit

CATEGORIES = [("shopping", "Shopping"), ("food_groceries", "Food & Groceries"), ("miscellaneous", "Miscellaneous")]
IDS = {"user_id": uuid7(), "upload_id": uuid7()}


def merchant(key: str) -> MerchantToLabel:
    return MerchantToLabel(
        key=key, merchant=key.upper(), description=None, original_category=None, amount=Decimal("-5.00")
    )


@pytest.fixture(autouse=True)
def no_langfuse():
    with patch("app.agents.transaction_labeler.labeler.create_trace_config", return_value={"metadata": {}}):
        yield


def answering(answer_for):
    """An ask_json stub: `answer_for(batch_items)` returns the parsed answer list for one batch."""

    async def fake(service, system, user, shape, config):
        return shape.model_validate(answer_for(json.loads(user)))

    return fake


async def test_a_known_merchant_skips_the_model():
    ask = AsyncMock()
    with patch("app.agents.transaction_labeler.labeler.ask_json", ask):
        result = await label([merchant("rewe")], CATEGORIES, **IDS)
    ask.assert_not_awaited()
    assert result.labels == {"rewe": Label("food_groceries", KNOWN_CONFIDENCE)}
    assert result.all_failed is False


async def test_the_model_labels_the_rest_by_slug_or_label():
    def answer(items):
        return [
            {"id": 0, "category": "shopping", "confidence": 0.9},
            {"id": 1, "category": "Food & Groceries", "confidence": 1.7},
        ]

    with patch("app.agents.transaction_labeler.labeler.ask_json", answering(answer)):
        result = await label([merchant("kiosk a"), merchant("kiosk b")], CATEGORIES, **IDS)
    assert result.labels == {"kiosk a": Label("shopping", 0.9), "kiosk b": Label("food_groceries", 1.0)}
    assert result.fallback_keys == set()


async def test_an_unknown_category_or_a_skipped_merchant_falls_back():
    def answer(items):
        return [{"id": 0, "category": "Groceries!", "confidence": 0.9}]

    with patch("app.agents.transaction_labeler.labeler.ask_json", answering(answer)):
        result = await label([merchant("kiosk a"), merchant("kiosk b")], CATEGORIES, **IDS)
    fallback = Label(FALLBACK_CATEGORY, FALLBACK_CONFIDENCE)
    assert result.labels == {"kiosk a": fallback, "kiosk b": fallback}
    assert result.fallback_keys == {"kiosk a", "kiosk b"}
    assert result.all_failed is False


async def test_merchants_go_in_batches_and_a_failed_batch_falls_back():
    merchants = [merchant(f"shop {i:03d}") for i in range(BATCH_SIZE + 1)]
    calls = []

    async def fake(service, system, user, shape, config):
        items = json.loads(user)
        calls.append(len(items))
        if len(items) == 1:
            raise LLMAPIError("down")
        return shape.model_validate([{"id": i, "category": "shopping", "confidence": 0.8} for i in range(len(items))])

    with patch("app.agents.transaction_labeler.labeler.ask_json", fake):
        result = await label(merchants, CATEGORIES, **IDS)
    assert sorted(calls) == [1, BATCH_SIZE]
    assert result.fallback_keys == {merchants[-1].key}
    assert result.all_failed is False


@pytest.mark.parametrize("error", [LLMAPIError("down"), InvalidModelAnswer("prose"), RuntimeError("no key")])
async def test_every_batch_failing_is_all_failed(error):
    with patch("app.agents.transaction_labeler.labeler.ask_json", AsyncMock(side_effect=error)):
        result = await label([merchant("kiosk a")], CATEGORIES, **IDS)
    assert result.all_failed is True
    assert result.labels["kiosk a"] == Label(FALLBACK_CATEGORY, FALLBACK_CONFIDENCE)


async def test_nothing_to_ask_is_not_a_failure():
    result = await label([], CATEGORIES, **IDS)
    assert (result.labels, result.all_failed) == ({}, False)


async def test_the_model_sees_amounts_as_decimals_and_the_banks_category():
    seen = {}

    async def fake(service, system, user, shape, config):
        seen["system"], seen["items"] = system, json.loads(user)
        return shape.model_validate([])

    item = MerchantToLabel(
        key="kiosk", merchant="KIOSK 24", description="Snacks", original_category="Food", amount=Decimal("-4.50")
    )
    with patch("app.agents.transaction_labeler.labeler.ask_json", fake):
        await label([item], CATEGORIES, **IDS)
    assert seen["items"] == [
        {"id": 0, "merchant": "KIOSK 24", "amount": "-4.50", "description": "Snacks", "bank_category": "Food"}
    ]
    assert "- shopping: Shopping" in seen["system"]

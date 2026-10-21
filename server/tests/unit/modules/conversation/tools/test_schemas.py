"""PeriodArgs: one kind of period, in bounds, and nothing the tool does not take."""

import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.conversation.tools import chat_tools
from app.modules.conversation.tools.analytics import PeriodArgs, TopMerchantsArgs
from app.modules.conversation.tools.search import SearchArgs, search_tool

pytestmark = pytest.mark.unit


def test_months_and_dates_together_are_rejected():
    with pytest.raises(ValidationError, match="either months or date_from/date_to, not both"):
        PeriodArgs.model_validate({"months": 3, "date_to": "2026-09-30"})


def test_no_period_is_rejected():
    with pytest.raises(ValidationError, match="give a period"):
        PeriodArgs.model_validate({})


@pytest.mark.parametrize("args", [{"months": 3}, {"date_from": "2026-09-01"}, {"date_to": "2026-09-30"}])
def test_months_or_a_date_bound_is_a_period(args):
    PeriodArgs.model_validate(args)


@pytest.mark.parametrize("months", [0, 121])
def test_months_outside_1_to_120_are_rejected(months):
    with pytest.raises(ValidationError, match="months"):
        PeriodArgs.model_validate({"months": months})


def test_a_date_outside_what_analytics_covers_is_rejected():
    with pytest.raises(ValidationError, match="date_from"):
        PeriodArgs.model_validate({"date_from": "1800-01-01"})


def test_an_argument_the_tool_does_not_take_is_rejected():
    # The user is never an argument: a smuggled user id fails validation instead of being ignored.
    with pytest.raises(ValidationError, match="user_id"):
        PeriodArgs.model_validate({"months": 1, "user_id": "someone-else"})


def test_dates_are_iso():
    args = PeriodArgs.model_validate({"date_from": "2026-07-01", "date_to": "2026-09-30"})
    assert (args.date_from, args.date_to) == (dt.date(2026, 7, 1), dt.date(2026, 9, 30))


def test_top_merchants_caps_its_ranking_at_15():
    assert TopMerchantsArgs.model_validate({"months": 1}).top_n == 10
    with pytest.raises(ValidationError, match="top_n"):
        TopMerchantsArgs.model_validate({"months": 1, "top_n": 16})


def _keys(node):
    """Every key anywhere in a JSON-schema document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _keys(item)


def test_no_tool_schema_sent_to_the_model_carries_a_regex_pattern():
    # Pydantic's Decimal schema has a lookahead `pattern`; with it, gpt-5-mini answers nothing at all.
    tools = chat_tools()
    assert tools
    for tool in tools:
        assert "pattern" not in set(_keys(tool.tool_call_schema.model_json_schema())), tool.name


def test_the_runtime_slot_is_not_part_of_the_schema_the_model_sees():
    for tool in chat_tools():
        assert "runtime" not in tool.tool_call_schema.model_json_schema()["properties"], tool.name


def test_arguments_validate_without_the_runtime():
    # The tool-events middleware pre-validates a call's arguments before the tool node injects the runtime.
    for tool in chat_tools():
        assert "runtime" in tool.args_schema.model_fields
    assert PeriodArgs.model_validate({"months": 1}).runtime is None


def test_amounts_are_json_numbers_in_the_schema_and_exact_decimals_after_parsing():
    props = search_tool().tool_call_schema.model_json_schema()["properties"]
    assert props["amount_min"]["anyOf"][0]["type"] == "number"
    args = SearchArgs.model_validate({"amount_min": -0.1, "amount_max": 12.35})
    assert (args.amount_min, args.amount_max) == (Decimal("-0.1"), Decimal("12.35"))


def test_an_inverted_amount_range_is_rejected():
    with pytest.raises(ValidationError, match="amount_min"):
        SearchArgs.model_validate({"amount_min": 5, "amount_max": 1})

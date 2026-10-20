"""PeriodArgs: one kind of period, in bounds, and nothing the tool does not take."""

import datetime as dt

import pytest
from pydantic import ValidationError

from app.modules.conversation.finance.schemas import PeriodArgs, TopMerchantsArgs

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

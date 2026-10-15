"""Count-matched duplicates (spec §4.4)."""

import pytest

from app.modules.transaction.domain import plan_count_matched

pytestmark = pytest.mark.unit


def test_nothing_held_keeps_every_copy():
    assert plan_count_matched(["a", "a", "b"], {}) == [True, True, True]


def test_held_copies_are_subtracted_from_the_first_ones():
    assert plan_count_matched(["a", "a", "b"], {"a": 1}) == [False, True, True]


def test_more_held_than_in_the_file_keeps_none():
    assert plan_count_matched(["a", "a", "b"], {"a": 5, "b": 1}) == [False, False, False]

"""The known-merchant table agrees with the transaction module it cannot import (R2)."""

import pytest

from app.agents.transaction_labeler.known_merchants import EXCLUDED, KNOWN_MERCHANTS, match_known
from app.modules.transaction import CATEGORIES
from app.modules.transaction.domain import normalise_merchant

pytestmark = pytest.mark.unit


def test_every_key_is_already_a_merchant_key():
    assert [k for k in KNOWN_MERCHANTS if normalise_merchant(k) != k] == []


def test_every_value_is_a_category_slug():
    slugs = {slug for slug, _ in CATEGORIES}
    assert {v for v in KNOWN_MERCHANTS.values()} <= slugs


@pytest.mark.parametrize(
    ("key", "slug"),
    [("netflix", "leisure_entertainment"), ("rewe markt", "food_groceries"), ("bvg", "transportation")],
)
def test_whole_words_match(key, slug):
    assert match_known(key) == slug


def test_a_word_inside_another_does_not_match():
    assert match_known("dmitri petrov") is None
    assert match_known("university of bologna") is None


def test_the_longest_name_wins():
    assert match_known("aldi süd filiale") == KNOWN_MERCHANTS["aldi süd"]


def test_the_users_exclusions_are_gone_and_db_stays():
    assert EXCLUDED.isdisjoint(KNOWN_MERCHANTS)
    assert "db" in KNOWN_MERCHANTS


@pytest.mark.parametrize("key", ["deutsche bank", "comdirect", "ing diba", "sparkasse berlin", "n26"])
def test_bank_names_are_not_matched(key):
    assert match_known(key) is None

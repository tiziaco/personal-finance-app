"""uuid_utils.compat.uuid7 — the app-side primary key generator."""

import uuid

import pytest
from uuid_utils.compat import uuid7

pytestmark = pytest.mark.unit


def test_returns_a_stdlib_uuid_that_sqlalchemy_can_bind():
    assert type(uuid7()) is uuid.UUID


def test_is_version_7():
    assert uuid7().version == 7


def test_is_time_ordered():
    ids = [uuid7() for _ in range(100)]
    assert ids == sorted(ids)

"""uuid.UUID values in a log event render as plain strings, not UUID('…')."""

import uuid

import pytest

from app.core.logging import add_context_to_event_dict, get_structlog_processors, stringify_uuids

pytestmark = pytest.mark.unit

VALUE = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")


def test_uuid_values_become_their_string():
    out = stringify_uuids(None, "info", {"event": "x", "user_id": VALUE, "count": 1, "name": None})

    assert out == {"event": "x", "user_id": str(VALUE), "count": 1, "name": None}


def test_uuids_inside_collections_become_their_string():
    out = stringify_uuids(
        None,
        "info",
        {"event": "x", "ids": [VALUE], "pair": (VALUE, 1), "nested": {"user_id": VALUE, "tags": ["a"]}},
    )

    assert out == {
        "event": "x",
        "ids": [str(VALUE)],
        "pair": (str(VALUE), 1),
        "nested": {"user_id": str(VALUE), "tags": ["a"]},
    }


def test_runs_after_the_bound_context_is_merged():
    """bind_context(user_id=user.id) stores a UUID; it must pass through this processor too."""
    processors = get_structlog_processors()

    assert processors.index(stringify_uuids) > processors.index(add_context_to_event_dict)

"""Tests for supplier linking extracted from JIT provisioning.

The linker is called from three places (JIT, user.created, and
organization_membership.created), so it must be idempotent: linking an
already-linked supplier to the same user changes nothing.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.supplier import Supplier
from app.models.user import User
from app.services.user.service import UserService, merge_clerk_metadata

pytestmark = pytest.mark.unit


def make_user(user_id: str = "user-uuid-1") -> User:
    return User(id=user_id, clerk_id="user_abc", email="a@b.com", org_id="org_1")


def make_supplier(contact_id=None) -> Supplier:
    return Supplier(id="sup_1", name="Acme", code="ACME", vat_number="IT123", contact_id=contact_id)


async def test_links_unlinked_supplier():
    user, supplier = make_user(), make_supplier(contact_id=None)
    session = AsyncMock()

    with (
        patch(
            "app.services.user.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.services.user.service.supplier_repository.set_contact_id",
            new=AsyncMock(side_effect=lambda s, sup, cid: setattr(sup, "contact_id", cid) or sup),
        ),
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()),
    ):
        result = await UserService().link_supplier_from_metadata(user, {"supplier_id": "sup_1"}, session)

    assert result == "sup_1"
    assert supplier.contact_id == "user-uuid-1"


async def test_does_not_steal_an_already_linked_supplier():
    user, supplier = make_user(), make_supplier(contact_id="someone-else")
    session = AsyncMock()

    with patch(
        "app.services.user.service.supplier_repository.get_by_id",
        new=AsyncMock(return_value=supplier),
    ):
        result = await UserService().link_supplier_from_metadata(user, {"supplier_id": "sup_1"}, session)

    assert result is None
    assert supplier.contact_id == "someone-else"


async def test_replace_flag_relinks_and_invalidates_the_displaced_contact():
    user, supplier = make_user(), make_supplier(contact_id="displaced-user")
    session = AsyncMock()

    with (
        patch(
            "app.services.user.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.services.user.service.supplier_repository.set_contact_id",
            new=AsyncMock(side_effect=lambda s, sup, cid: setattr(sup, "contact_id", cid) or sup),
        ),
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()) as inval,
    ):
        result = await UserService().link_supplier_from_metadata(
            user, {"supplier_id": "sup_1", "replace": True}, session
        )

    assert result == "sup_1"
    invalidated = {c.kwargs.get("user_id") for c in inval.await_args_list}
    assert invalidated == {"displaced-user", "user-uuid-1"}


async def test_relinking_same_user_is_idempotent():
    """A retried webhook must not thrash the cache for an unchanged link."""
    user, supplier = make_user(), make_supplier(contact_id="user-uuid-1")
    session = AsyncMock()

    with (
        patch(
            "app.services.user.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.services.user.service.supplier_repository.set_contact_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()),
    ):
        result = await UserService().link_supplier_from_metadata(
            user, {"supplier_id": "sup_1", "replace": True}, session
        )

    assert result == "sup_1"
    assert supplier.contact_id == "user-uuid-1"


async def test_calling_twice_with_same_inputs_does_not_relink_or_double_invalidate():
    """Proves idempotency across repeated calls, not just a single steady-state call.

    A replayed webhook within svix's tolerance window must converge, not
    duplicate: the second call must be a pure no-op on both the row and the
    cache.
    """
    user, supplier = make_user(), make_supplier(contact_id=None)
    session = AsyncMock()

    with (
        patch(
            "app.services.user.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.services.user.service.supplier_repository.set_contact_id",
            new=AsyncMock(side_effect=lambda s, sup, cid: setattr(sup, "contact_id", cid) or sup),
        ) as set_contact_id,
        patch("app.services.user.service.user_cache.invalidate_user", new=AsyncMock()) as inval,
    ):
        first = await UserService().link_supplier_from_metadata(user, {"supplier_id": "sup_1"}, session)
        assert first == "sup_1"
        assert supplier.contact_id == "user-uuid-1"
        assert set_contact_id.await_count == 1
        assert inval.await_count == 1

        second = await UserService().link_supplier_from_metadata(user, {"supplier_id": "sup_1"}, session)

    assert second is None
    assert supplier.contact_id == "user-uuid-1"
    # No further DB write and no further cache invalidation on the replay.
    assert set_contact_id.await_count == 1
    assert inval.await_count == 1


async def test_no_metadata_is_a_noop():
    session = AsyncMock()
    assert await UserService().link_supplier_from_metadata(make_user(), {}, session) is None


class FakeMembership:
    def __init__(self, metadata):
        self.public_metadata = metadata


class FakeClerkUser:
    def __init__(self, top, memberships):
        self.public_metadata = top
        self.organization_memberships = memberships


def test_merge_prefers_top_level_over_membership_metadata():
    clerk_user = FakeClerkUser({"supplier_id": "top"}, [FakeMembership({"supplier_id": "membership"})])
    assert merge_clerk_metadata(clerk_user)["supplier_id"] == "top"


def test_merge_falls_back_to_membership_metadata():
    clerk_user = FakeClerkUser({}, [FakeMembership({"supplier_id": "membership", "replace": True})])
    merged = merge_clerk_metadata(clerk_user)
    assert merged["supplier_id"] == "membership"
    assert merged["replace"] is True


def test_merge_tolerates_missing_attributes():
    class Bare:
        pass

    assert merge_clerk_metadata(Bare()) == {}

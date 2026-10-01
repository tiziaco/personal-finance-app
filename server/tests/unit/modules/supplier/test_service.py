"""Tests for supplier linking extracted from JIT provisioning.

The linker is called from three places (JIT, user.created, and
organization_membership.created), so it must be idempotent: linking an
already-linked supplier to the same user changes nothing.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.supplier.models import Supplier
from app.modules.supplier.service import SupplierService

pytestmark = pytest.mark.unit

USER_1 = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")
USER_2 = uuid.UUID("0199a8b0-0000-7000-8000-000000000002")
SOMEONE_ELSE = uuid.UUID("0199a8b0-0000-7000-8000-000000000003")
SUPPLIER_ID = uuid.UUID("0199a8b0-0000-7000-8000-0000000000aa")


def make_supplier(contact_id=None) -> Supplier:
    return Supplier(id=SUPPLIER_ID, name="Acme", code="ACME", vat_number="IT123", contact_id=contact_id)


async def test_links_unlinked_supplier():
    supplier = make_supplier(contact_id=None)
    session = AsyncMock()

    with (
        patch(
            "app.modules.supplier.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.modules.supplier.service.supplier_repository.set_contact_id",
            new=AsyncMock(side_effect=lambda s, sup, cid: setattr(sup, "contact_id", cid) or sup),
        ),
        patch("app.modules.supplier.service.supplier_cache.invalidate_user", new=AsyncMock()),
    ):
        result = await SupplierService().link_from_metadata(session, USER_1, {"supplier_id": str(SUPPLIER_ID)})

    assert result == SUPPLIER_ID
    assert supplier.contact_id == USER_1


async def test_does_not_steal_an_already_linked_supplier():
    supplier = make_supplier(contact_id=SOMEONE_ELSE)
    session = AsyncMock()

    with patch(
        "app.modules.supplier.service.supplier_repository.get_by_id",
        new=AsyncMock(return_value=supplier),
    ):
        result = await SupplierService().link_from_metadata(session, USER_1, {"supplier_id": str(SUPPLIER_ID)})

    assert result is None
    assert supplier.contact_id == SOMEONE_ELSE


async def test_replace_flag_relinks_and_invalidates_the_displaced_contact():
    supplier = make_supplier(contact_id=USER_2)
    session = AsyncMock()

    with (
        patch(
            "app.modules.supplier.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.modules.supplier.service.supplier_repository.set_contact_id",
            new=AsyncMock(side_effect=lambda s, sup, cid: setattr(sup, "contact_id", cid) or sup),
        ),
        patch("app.modules.supplier.service.supplier_cache.invalidate_user", new=AsyncMock()) as inval,
    ):
        result = await SupplierService().link_from_metadata(
            session, USER_1, {"supplier_id": str(SUPPLIER_ID), "replace": True}
        )

    assert result == SUPPLIER_ID
    invalidated = {c.kwargs.get("user_id") for c in inval.await_args_list}
    assert invalidated == {USER_2, USER_1}


async def test_relinking_same_user_is_idempotent():
    """A retried webhook must not thrash the cache for an unchanged link."""
    supplier = make_supplier(contact_id=USER_1)
    session = AsyncMock()

    with (
        patch(
            "app.modules.supplier.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.modules.supplier.service.supplier_repository.set_contact_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch("app.modules.supplier.service.supplier_cache.invalidate_user", new=AsyncMock()),
    ):
        result = await SupplierService().link_from_metadata(
            session, USER_1, {"supplier_id": str(SUPPLIER_ID), "replace": True}
        )

    assert result == SUPPLIER_ID
    assert supplier.contact_id == USER_1


async def test_calling_twice_with_same_inputs_does_not_relink_or_double_invalidate():
    """Proves idempotency across repeated calls, not just a single steady-state call.

    A replayed webhook within svix's tolerance window must converge, not
    duplicate: the second call must be a pure no-op on both the row and the
    cache.
    """
    supplier = make_supplier(contact_id=None)
    session = AsyncMock()

    with (
        patch(
            "app.modules.supplier.service.supplier_repository.get_by_id",
            new=AsyncMock(return_value=supplier),
        ),
        patch(
            "app.modules.supplier.service.supplier_repository.set_contact_id",
            new=AsyncMock(side_effect=lambda s, sup, cid: setattr(sup, "contact_id", cid) or sup),
        ) as set_contact_id,
        patch("app.modules.supplier.service.supplier_cache.invalidate_user", new=AsyncMock()) as inval,
    ):
        first = await SupplierService().link_from_metadata(session, USER_1, {"supplier_id": str(SUPPLIER_ID)})
        assert first == SUPPLIER_ID
        assert supplier.contact_id == USER_1
        assert set_contact_id.await_count == 1
        assert inval.await_count == 1

        second = await SupplierService().link_from_metadata(session, USER_1, {"supplier_id": str(SUPPLIER_ID)})

    assert second is None
    assert supplier.contact_id == USER_1
    # No further DB write and no further cache invalidation on the replay.
    assert set_contact_id.await_count == 1
    assert inval.await_count == 1


async def test_no_metadata_is_a_noop():
    session = AsyncMock()
    assert await SupplierService().link_from_metadata(session, USER_1, {}) is None


@pytest.mark.parametrize("raw", ["sup_1", "not-a-uuid", "", 123, ["x"]])
async def test_a_malformed_supplier_id_links_nothing_and_does_not_raise(raw):
    """Metadata is set by hand in the Clerk dashboard; a typo must not fail every sync for that user."""
    get_by_id = AsyncMock()

    with patch("app.modules.supplier.service.supplier_repository.get_by_id", new=get_by_id):
        result = await SupplierService().link_from_metadata(AsyncMock(), USER_1, {"supplier_id": raw})

    assert result is None
    get_by_id.assert_not_awaited()

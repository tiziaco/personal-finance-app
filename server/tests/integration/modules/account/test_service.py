"""Integration tests for UserService — JIT provisioning with mocked Clerk, real DB."""

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from app.integrations.clerk.exceptions import ClerkUserNotFoundError
from app.modules.account.cache import user_cache
from app.modules.account.models import User
from app.modules.account.service import UserService
from app.modules.supplier import supplier_service
from app.modules.supplier.cache import supplier_cache
from app.modules.supplier.models import Supplier
from app.utils.cache import MISS

pytestmark = pytest.mark.integration


@pytest.fixture
def service():
    return UserService


@pytest.fixture
async def existing_user(db_session):
    """A user that already exists in the database."""
    user = User(
        clerk_id="clerk_provider_existing",
        org_id="test_org_123",
        email="provider_existing@example.com",
        first_name="Existing",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


class TestDbHit:
    """Tests for resolve_user when the user already exists in the DB."""

    async def test_db_hit_returns_user_without_calling_clerk(self, service, db_session, existing_user):
        with patch("app.modules.account.service.clerk_client.get_user") as mock_get:
            user = await service.resolve_user(db_session, existing_user.clerk_id, "test_org_123")
            mock_get.assert_not_called()

        assert user.id == existing_user.id
        assert user.clerk_id == existing_user.clerk_id

    async def test_db_hit_syncs_org_id(self, service, db_session, existing_user):
        with patch("app.modules.account.service.clerk_client.get_user"):
            user = await service.resolve_user(db_session, existing_user.clerk_id, "org_moved")

        assert user.org_id == "org_moved"


class TestJITProvisioning:
    """Tests for JIT provisioning path — user not in cache or DB."""

    def _make_clerk_user(self, clerk_id, email="jit@example.com"):
        clerk_user = MagicMock()
        clerk_user.first_name = "JIT"
        clerk_user.last_name = "User"
        clerk_user.image_url = None
        clerk_user.primary_email_address_id = "email_abc"
        return clerk_user

    @patch("app.modules.account.service.clerk_client.get_primary_email")
    @patch("app.modules.account.service.clerk_client.get_user")
    async def test_jit_creates_user_in_db(self, mock_get_user, mock_get_email, service, db_session):
        clerk_id = "clerk_jit_new_001"
        mock_get_user.return_value = self._make_clerk_user(clerk_id)
        mock_get_email.return_value = "jit_new@example.com"

        user = await service.resolve_user(db_session, clerk_id, "test_org_123")

        assert user.clerk_id == clerk_id
        assert user.email == "jit_new@example.com"
        assert user.id is not None

    @patch("app.modules.account.service.clerk_client.get_user")
    async def test_clerk_not_found_raises(self, mock_get_user, service, db_session):
        mock_get_user.side_effect = ClerkUserNotFoundError("not found")

        with pytest.raises(ClerkUserNotFoundError):
            await service.resolve_user(db_session, "clerk_nonexistent_jit", "test_org_123")


class TestSupplierRelinkInvalidation:
    """Re-linking a supplier must invalidate BOTH users' cached links.

    The displaced contact is the interesting one: their cached
    user_id -> supplier_id entry is wrong the moment contact_id is
    reassigned, and the old id is discarded by the overwrite.
    """

    def _make_clerk_user(self, supplier_id, replace):
        clerk_user = MagicMock()
        clerk_user.first_name = "New"
        clerk_user.last_name = "Contact"
        clerk_user.image_url = None
        clerk_user.primary_email_address_id = "email_abc"
        clerk_user.public_metadata = {"supplier_id": supplier_id}
        if replace:
            clerk_user.public_metadata["replace"] = True
        return clerk_user

    @pytest_asyncio.fixture
    async def linked_supplier(self, db_session, existing_user):
        """A supplier already linked to `existing_user`."""
        supplier = Supplier(
            contact_id=existing_user.id,
            name="Acme Forgings",
            code="ACME-001",
            vat_number="IT01234567890",
        )
        db_session.add(supplier)
        await db_session.flush()
        await db_session.refresh(supplier)
        return supplier

    @patch("app.modules.account.service.clerk_client.get_primary_email")
    @patch("app.modules.account.service.clerk_client.get_user")
    async def test_replace_displaces_old_contact_and_clears_its_cache(
        self,
        mock_get_user,
        mock_get_email,
        service,
        db_session,
        existing_user,
        linked_supplier,
    ):
        # The displaced user has their link cached from an earlier request
        await supplier_cache.set_supplier_id(existing_user.id, linked_supplier.id)

        mock_get_user.return_value = self._make_clerk_user(linked_supplier.id, replace=True)
        mock_get_email.return_value = "new_contact@example.com"

        new_user = await service.resolve_user(db_session, "clerk_replacement_001", "test_org_123")

        assert linked_supplier.contact_id == new_user.id
        assert await supplier_cache.get_supplier_id(existing_user.id) is MISS
        # And re-reading goes to the DB, which now says "not linked"
        assert await supplier_service.get_id_for_user(db_session, existing_user.id) is None

    @patch("app.modules.account.service.clerk_client.get_primary_email")
    @patch("app.modules.account.service.clerk_client.get_user")
    async def test_new_contact_link_is_readable(
        self,
        mock_get_user,
        mock_get_email,
        service,
        db_session,
        existing_user,
        linked_supplier,
    ):
        mock_get_user.return_value = self._make_clerk_user(linked_supplier.id, replace=True)
        mock_get_email.return_value = "new_contact@example.com"

        new_user = await service.resolve_user(db_session, "clerk_replacement_002", "test_org_123")

        assert await supplier_service.get_id_for_user(db_session, new_user.id) == linked_supplier.id

    @patch("app.modules.account.service.clerk_client.get_primary_email")
    @patch("app.modules.account.service.clerk_client.get_user")
    async def test_without_replace_flag_old_contact_is_untouched(
        self,
        mock_get_user,
        mock_get_email,
        service,
        db_session,
        existing_user,
        linked_supplier,
    ):
        await supplier_cache.set_supplier_id(existing_user.id, linked_supplier.id)

        mock_get_user.return_value = self._make_clerk_user(linked_supplier.id, replace=False)
        mock_get_email.return_value = "hopeful@example.com"

        await service.resolve_user(db_session, "clerk_no_replace_001", "test_org_123")

        # contact_id guard held, so nothing was displaced and nothing invalidated
        assert linked_supplier.contact_id == existing_user.id
        assert await supplier_cache.get_supplier_id(existing_user.id) == linked_supplier.id

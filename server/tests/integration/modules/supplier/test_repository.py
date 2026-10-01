"""Integration tests for SupplierRepository — CRUD against real test database."""

from datetime import UTC, datetime

import pytest
from uuid_utils.compat import uuid7

from app.modules.account.models import User
from app.modules.supplier.models import Supplier
from app.modules.supplier.repository import SupplierRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def contact_user(db_session):
    """A user available to link as a supplier's contact."""
    user = User(
        clerk_id="clerk_supplier_repo_contact",
        org_id="test_org_123",
        email="supplier_repo_contact@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def saved_supplier(db_session):
    """A committed supplier with no contact linked."""
    supplier = Supplier(
        name="Repo Test Supplier",
        code="REPO-001",
        vat_number="IT00000000001",
    )
    db_session.add(supplier)
    await db_session.flush()
    await db_session.refresh(supplier)
    return supplier


class TestGetById:
    """Tests for SupplierRepository.get_by_id()."""

    async def test_get_by_id_found(self, db_session, saved_supplier):
        found = await SupplierRepository.get_by_id(db_session, saved_supplier.id)
        assert found is not None
        assert found.id == saved_supplier.id

    async def test_get_by_id_not_found(self, db_session):
        found = await SupplierRepository.get_by_id(db_session, uuid7())
        assert found is None


class TestGetIdByContactId:
    """Tests for SupplierRepository.get_id_by_contact_id()."""

    async def test_linked_non_deleted_supplier_returns_id(self, db_session, saved_supplier, contact_user):
        saved_supplier.contact_id = contact_user.id
        db_session.add(saved_supplier)
        await db_session.flush()

        found_id = await SupplierRepository.get_id_by_contact_id(db_session, contact_user.id)
        assert found_id == saved_supplier.id

    async def test_no_link_returns_none(self, db_session, contact_user):
        found_id = await SupplierRepository.get_id_by_contact_id(db_session, contact_user.id)
        assert found_id is None

    async def test_linked_but_soft_deleted_supplier_returns_none(self, db_session, saved_supplier, contact_user):
        saved_supplier.contact_id = contact_user.id
        saved_supplier.deleted_at = datetime.now(UTC)
        db_session.add(saved_supplier)
        await db_session.flush()

        found_id = await SupplierRepository.get_id_by_contact_id(db_session, contact_user.id)
        assert found_id is None


class TestGetByContactId:
    """Tests for SupplierRepository.get_by_contact_id()."""

    async def test_linked_supplier_returns_full_row(self, db_session, saved_supplier, contact_user):
        saved_supplier.contact_id = contact_user.id
        db_session.add(saved_supplier)
        await db_session.flush()

        found = await SupplierRepository.get_by_contact_id(db_session, contact_user.id)
        assert found is not None
        assert found.id == saved_supplier.id

    async def test_no_link_returns_none(self, db_session, contact_user):
        found = await SupplierRepository.get_by_contact_id(db_session, contact_user.id)
        assert found is None

    async def test_returns_supplier_even_if_soft_deleted(self, db_session, saved_supplier, contact_user):
        saved_supplier.contact_id = contact_user.id
        saved_supplier.deleted_at = datetime.now(UTC)
        db_session.add(saved_supplier)
        await db_session.flush()

        found = await SupplierRepository.get_by_contact_id(db_session, contact_user.id)
        assert found is not None
        assert found.id == saved_supplier.id


class TestSetContactId:
    """Tests for SupplierRepository.set_contact_id()."""

    async def test_sets_contact_id(self, db_session, saved_supplier, contact_user):
        updated = await SupplierRepository.set_contact_id(db_session, saved_supplier, contact_user.id)
        assert updated.contact_id == contact_user.id

    async def test_clears_contact_id(self, db_session, saved_supplier, contact_user):
        saved_supplier.contact_id = contact_user.id
        db_session.add(saved_supplier)
        await db_session.flush()

        updated = await SupplierRepository.set_contact_id(db_session, saved_supplier, None)
        assert updated.contact_id is None

    async def test_persists(self, db_session, saved_supplier, contact_user):
        await SupplierRepository.set_contact_id(db_session, saved_supplier, contact_user.id)
        found = await SupplierRepository.get_by_id(db_session, saved_supplier.id)
        assert found.contact_id == contact_user.id

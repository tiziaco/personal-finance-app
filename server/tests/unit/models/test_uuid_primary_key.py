"""Every table's key: UUID v7, native uuid column, uuidv7() server default, one column per table."""

import uuid

import pytest
import sqlalchemy as sa

from app.modules.account.models import User
from app.modules.conversation.models import Conversation
from app.modules.supplier.models import Supplier

pytestmark = pytest.mark.unit

TABLES = [User, Supplier, Conversation]
NEW_ROW = {
    User: lambda: User(clerk_id="clerk_pk", email="pk@example.com"),
    Supplier: lambda: Supplier(name="Acme", code="ACME", vat_number="IT1"),
    Conversation: lambda: Conversation(user_id=uuid.uuid4()),
}


@pytest.mark.parametrize("model", TABLES, ids=lambda m: m.__name__)
def test_id_is_a_native_uuid_with_a_uuidv7_server_default(model):
    column = model.__table__.c.id

    assert column.primary_key
    assert isinstance(column.type, sa.Uuid)
    assert str(column.server_default.arg) == "uuidv7()"


def test_each_table_owns_its_id_column():
    columns = [model.__table__.c.id for model in TABLES]

    assert len({id(column) for column in columns}) == len(TABLES)


@pytest.mark.parametrize("model", TABLES, ids=lambda m: m.__name__)
def test_a_new_row_has_a_v7_id_before_flush(model):
    row = NEW_ROW[model]()

    assert isinstance(row.id, uuid.UUID)
    assert row.id.version == 7


@pytest.mark.parametrize(
    "column", [Conversation.__table__.c.user_id, Supplier.__table__.c.contact_id], ids=lambda c: c.name
)
def test_foreign_keys_to_user_are_native_uuids(column):
    assert isinstance(column.type, sa.Uuid)

"""Erasure removes the user's remembered mappings and held upload, and only theirs."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from app.modules.transaction.imports import handlers
from app.modules.transaction.imports.models import HeldUpload, MappingProfile

pytestmark = pytest.mark.integration


async def _seed(db_session, user):
    db_session.add(MappingProfile(user_id=user.id, column_key="a" * 64, mapping={"Betrag": "amount"}))
    db_session.add(
        HeldUpload(user_id=user.id, content="a,b\n1,2\n", expires_at=datetime.now(UTC) + timedelta(minutes=30))
    )
    await db_session.flush()


async def test_erasure_deletes_profiles_and_the_held_upload(db_session, test_user, other_user):
    await _seed(db_session, test_user)
    await _seed(db_session, other_user)

    await handlers.erase_imports_on_user_erasing(session=db_session, user_id=test_user.id)

    profiles = (await db_session.execute(select(MappingProfile.user_id))).scalars().all()
    uploads = (await db_session.execute(select(HeldUpload.user_id))).scalars().all()
    assert profiles == [other_user.id]
    assert uploads == [other_user.id]

"""The seed against the container database, with the real seed file."""

import sys
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import func, select

from app.modules.transaction.models import Transaction

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from seed_transactions import SEED_FILE, seed  # noqa: E402

pytestmark = pytest.mark.integration

TODAY = date(2026, 10, 13)


async def test_seeds_the_file_within_the_shifted_range_and_reseeding_resets(db_session, test_user):
    count = await seed(db_session, test_user.clerk_id, TODAY)
    assert count > 900
    newest, oldest = (await db_session.execute(select(func.max(Transaction.date), func.min(Transaction.date)))).one()
    assert newest <= TODAY and (newest.year, newest.month) == (2026, 10)
    assert oldest < date(2024, 1, 1)

    assert await seed(db_session, test_user.clerk_id, TODAY) == count
    total = (await db_session.execute(select(func.count()).select_from(Transaction))).scalar_one()
    assert total == count
    assert SEED_FILE.exists()

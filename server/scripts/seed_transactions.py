"""Fill a dev user's transactions from server/data/transactions-seed.csv.

Development only. Replaces the user's transactions — rerunning resets them.
Dates move forward by whole months so the newest row falls in the current
month (the day of month is kept, clamped to the month's length); a row that
would land after today is dropped. A slug the category list no longer has is
filed under miscellaneous, and reported.

    make -C server seed-transactions CLERK_ID=user_...
"""

import argparse
import asyncio
import calendar
import csv
import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Environment, settings
from app.core.logging import logger
from app.database import close_database_engine, create_session_factory, initialize_database_engine
from app.modules.account import user_service
from app.modules.transaction import Category, TransactionImport, transaction_service

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "transactions-seed.csv"
_SLUGS = {c.value for c in Category}


def shift_months(d: date, months: int) -> date:
    """`d` moved forward `months` whole months, its day clamped to the target month's length."""
    index = d.year * 12 + (d.month - 1) + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def months_to_current(newest: date, today: date) -> int:
    """Whole months from `newest`'s month to `today`'s."""
    return (today.year * 12 + today.month) - (newest.year * 12 + newest.month)


def load_rows(path: Path, today: date) -> tuple[list[TransactionImport], Counter]:
    """The seed rows, dates shifted, rows after today dropped; plus a count of unknown slugs.

    Only a `true` is_recurring cell is the user's tick; anything else is None, left to the recurring rule.
    """
    with path.open(encoding="utf-8", newline="") as f:
        raw = list(csv.DictReader(f))
    if not raw:
        return [], Counter()
    months = months_to_current(max(date.fromisoformat(r["date"]) for r in raw), today)
    unknown: Counter = Counter()
    rows: list[TransactionImport] = []
    for r in raw:
        shifted = shift_months(date.fromisoformat(r["date"]), months)
        if shifted > today:
            continue
        category = r["category"]
        if category not in _SLUGS:
            unknown[category] += 1
            category = "miscellaneous"
        rows.append(
            TransactionImport(
                date=shifted,
                merchant=r["merchant"],
                amount=Decimal(r["amount"]),
                description=r["description"] or None,
                category=category,
                confidence=float(r["confidence"]),
                is_recurring=True if r["is_recurring"] == "true" else None,
                original_category=r["original_category"] or None,
            )
        )
    return rows, unknown


async def seed(session: AsyncSession, clerk_id: str, today: date, path: Path = SEED_FILE) -> int:
    """Replace the user's transactions with the seed. Resolves the user as a request would (JIT from Clerk)."""
    user = await user_service.resolve_user(session, clerk_id)
    rows, unknown = load_rows(path, today)
    if unknown:
        print(f"warning: filed under miscellaneous, slugs no longer in the list: {dict(unknown)}", file=sys.stderr)
    await transaction_service.delete_all_for_user(session, user.id)
    count = await transaction_service.import_many(session, user.id, rows)
    logger.info("transactions_seeded", user_id=user.id, count=count)
    return count


async def _main(clerk_id: str) -> None:
    engine = await initialize_database_engine()
    try:
        async with create_session_factory(engine)() as session:
            count = await seed(session, clerk_id, date.today())
            await session.commit()
        print(f"seeded {count} transactions for {clerk_id}")
    finally:
        await close_database_engine(engine)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clerk-id", required=True, help="The Clerk user id (user_...) to seed")
    args = parser.parse_args()
    if settings.ENVIRONMENT != Environment.DEVELOPMENT:
        sys.exit(f"refusing to seed: APP_ENV is {settings.ENVIRONMENT.value}, not development")
    asyncio.run(_main(args.clerk_id))

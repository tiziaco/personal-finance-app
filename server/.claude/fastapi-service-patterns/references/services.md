# Service Classes

Services are **stateless classes with static async methods**. They contain business logic and coordinate between the database and external APIs. Each service module exports a **module-level singleton**.

```python
# app/services/payment/service.py

class PaymentService:
    """Stateless service for payment operations."""

    @staticmethod
    async def get(db: AsyncSession, user_id: str, payment_id: int) -> Payment:
        stmt = select(Payment).where(
            Payment.id == payment_id,
            Payment.user_id == user_id,
            Payment.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()
        if not payment:
            raise PaymentNotFoundError(
                f"Payment {payment_id} not found",
                payment_id=payment_id,
            )
        return payment

    @staticmethod
    async def create(db: AsyncSession, user_id: str, data: PaymentCreate) -> Payment:
        payment = Payment(user_id=user_id, **data.model_dump())
        db.add(payment)
        await db.flush()
        await db.refresh(payment)
        logger.info("payment_created", user_id=user_id, payment_id=payment.id)
        return payment

    @staticmethod
    async def update(
        db: AsyncSession,
        user_id: str,
        payment_id: int,
        data: PaymentUpdate,
    ) -> Payment:
        payment = await PaymentService.get(db, user_id, payment_id)
        update_fields = data.model_dump(exclude_unset=True)  # Only provided fields
        for field, value in update_fields.items():
            setattr(payment, field, value)
        await db.flush()
        await db.refresh(payment)
        logger.info("payment_updated", user_id=user_id, payment_id=payment_id, fields=list(update_fields))
        return payment

    @staticmethod
    async def delete(db: AsyncSession, user_id: str, payment_id: int) -> None:
        payment = await PaymentService.get(db, user_id, payment_id)
        payment.deleted_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info("payment_deleted", user_id=user_id, payment_id=payment_id)

    @staticmethod
    async def list(
        db: AsyncSession,
        user_id: str,
        filters: PaymentFilters,
        offset: int,
        limit: int,
    ) -> tuple[list[Payment], int]:
        stmt = (
            select(Payment)
            .where(Payment.user_id == user_id, Payment.deleted_at.is_(None))
            .offset(offset)
            .limit(limit)
        )
        # Apply filters here...
        result = await db.execute(stmt)
        items = list(result.scalars().all())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        return items, total


# Singleton — import and use this, don't re-instantiate in routes
payment_service = PaymentService()
```

## Rules

- All methods are `@staticmethod` and `async` — services hold no state
- Parameter order: `db` first, then `user_id`, then domain params/data
- `flush()` + `refresh()` after writes — never `commit()` (the `get_db_session` dependency commits)
- Soft-delete: set `deleted_at = datetime.now(timezone.utc)`, never issue a `DELETE`
- Soft-delete queries always filter `deleted_at.is_(None)`
- PATCH updates use `model_dump(exclude_unset=True)` — only write fields the caller actually sent
- Log significant mutations with structured key=value pairs (`logger.info`, `logger.warning`)
- Never return `None` — raise a domain exception if the resource doesn't exist

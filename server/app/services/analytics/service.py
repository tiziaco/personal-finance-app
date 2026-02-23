"""Analytics service — data bridge between the DB and analytics tools."""

from datetime import date, datetime
from typing import Any, Dict, Optional

import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.models.transaction import Transaction
from app.services.analytics.exceptions import AnalyticsError
from app.tools.financial import (
    get_anomaly_insights,
    get_behavioral_patterns,
    get_category_insights,
    get_merchant_insights,
    get_recurring_insights,
    get_spending_stability_profile,
    get_spending_summary,
    get_trend_insights,
)


class AnalyticsService:
    """Stateless analytics service.

    Bridges DB → Polars DataFrame and delegates to semantic tools in
    app/tools/financial.py. No analytics logic lives here.
    """

    @staticmethod
    async def load_dataframe(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> pl.DataFrame:
        """Fetch non-deleted user transactions and return as a Polars DataFrame.

        Applies date filter at the DB level for efficiency.
        Returns a typed empty DataFrame (correct schema) when no rows match.

        Args:
            db: Database session.
            user_id: ID of the authenticated user.
            date_from: Optional inclusive start date (DB-level filter).
            date_to: Optional inclusive end date (DB-level filter).

        Returns:
            pl.DataFrame with columns: date (Date), merchant (Utf8),
            amount (Float64), category (Utf8), confidence_score (Float64),
            is_recurring (Boolean).
        """
        empty_schema = {
            "date": pl.Date,
            "merchant": pl.Utf8,
            "amount": pl.Float64,
            "category": pl.Utf8,
            "confidence_score": pl.Float64,
            "is_recurring": pl.Boolean,
        }

        conditions = [
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        ]
        if date_from:
            conditions.append(Transaction.date >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            conditions.append(Transaction.date <= datetime.combine(date_to, datetime.max.time()))

        stmt = select(Transaction).where(*conditions).order_by(Transaction.date)
        result = await db.execute(stmt)
        transactions = result.scalars().all()

        if not transactions:
            return pl.DataFrame(schema=empty_schema)

        rows = [
            {
                "date": t.date.date() if isinstance(t.date, datetime) else t.date,
                "merchant": t.merchant,
                "amount": float(t.amount),
                "category": t.category.value,
                "confidence_score": float(t.confidence_score),
                "is_recurring": t.is_recurring,
            }
            for t in transactions
        ]

        logger.debug(
            "analytics_dataframe_loaded",
            user_id=user_id,
            rows=len(rows),
        )
        return pl.DataFrame(rows)

    @staticmethod
    async def get_dashboard(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Compose a summary across 4 domains for the dashboard."""
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            spending = await get_spending_summary(df, start_date=date_from, end_date=date_to)
            categories = await get_category_insights(df, start_date=date_from, end_date=date_to)
            recurring = await get_recurring_insights(df, start_date=date_from, end_date=date_to)
            trends = await get_trend_insights(df, start_date=date_from, end_date=date_to)
        except Exception as e:
            raise AnalyticsError(f"Dashboard analytics failed: {e}") from e

        return {
            "spending": spending,
            "categories": categories,
            "recurring": recurring,
            "trends": trends,
        }

    @staticmethod
    async def get_spending(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_spending_summary(df, start_date=date_from, end_date=date_to)
        except Exception as e:
            raise AnalyticsError(f"Spending analytics failed: {e}") from e

    @staticmethod
    async def get_categories(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        top_n: int = 10,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_category_insights(df, start_date=date_from, end_date=date_to, top_n=top_n)
        except Exception as e:
            raise AnalyticsError(f"Category analytics failed: {e}") from e

    @staticmethod
    async def get_merchants(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        top_n: int = 15,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_merchant_insights(df, start_date=date_from, end_date=date_to, top_n=top_n)
        except Exception as e:
            raise AnalyticsError(f"Merchant analytics failed: {e}") from e

    @staticmethod
    async def get_recurring(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            recurring = await get_recurring_insights(df, start_date=date_from, end_date=date_to)
            stability = await get_spending_stability_profile(df, start_date=date_from, end_date=date_to)
            return {"recurring": recurring, "stability": stability}
        except Exception as e:
            raise AnalyticsError(f"Recurring analytics failed: {e}") from e

    @staticmethod
    async def get_behavior(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_behavioral_patterns(df, start_date=date_from, end_date=date_to)
        except Exception as e:
            raise AnalyticsError(f"Behavioral analytics failed: {e}") from e

    @staticmethod
    async def get_anomalies(
        db: AsyncSession,
        user_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        std_threshold: float = 2.5,
        rolling_window: int = 30,
    ) -> Dict[str, Any]:
        df = await AnalyticsService.load_dataframe(db, user_id, date_from, date_to)
        try:
            return await get_anomaly_insights(
                df,
                start_date=date_from,
                end_date=date_to,
                std_threshold=std_threshold,
                rolling_window=rolling_window,
            )
        except Exception as e:
            raise AnalyticsError(f"Anomaly analytics failed: {e}") from e


analytics_service = AnalyticsService()

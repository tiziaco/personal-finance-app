"""Transaction service."""

from app.modules.transaction.schemas import CATEGORIES, CategoryResponse


class TransactionService:
    """Orchestrates transaction operations."""

    @staticmethod
    def list_categories() -> list[CategoryResponse]:
        """Every category, in display order."""
        return [CategoryResponse(value=slug, label=label) for slug, label in CATEGORIES]


transaction_service = TransactionService()

"""The transaction labeller (docs/product/features/categorisation.md)."""

from app.agents.transaction_labeler.labeler import (
    BATCH_SIZE,
    FALLBACK_CATEGORY,
    FALLBACK_CONFIDENCE,
    KNOWN_CONFIDENCE,
    MAX_CONCURRENT_BATCHES,
    Label,
    LabelResult,
    MerchantToLabel,
    label,
)

__all__ = [
    "BATCH_SIZE",
    "FALLBACK_CATEGORY",
    "FALLBACK_CONFIDENCE",
    "KNOWN_CONFIDENCE",
    "MAX_CONCURRENT_BATCHES",
    "Label",
    "LabelResult",
    "MerchantToLabel",
    "label",
]

"""Count-matched duplicates for an import (docs/data-model/transaction.md, D3)."""

from collections import Counter


def plan_count_matched(fingerprints: list[str], existing: dict[str, int]) -> list[bool]:
    """Which rows of a file to keep: a fingerprint held k times keeps all but its first k copies.

    Two identical coffees in a file import as two; re-importing the same file
    imports nothing. `existing` counts the user's active rows per fingerprint.
    """
    seen: Counter[str] = Counter()
    keep = []
    for fingerprint in fingerprints:
        seen[fingerprint] += 1
        keep.append(seen[fingerprint] > existing.get(fingerprint, 0))
    return keep

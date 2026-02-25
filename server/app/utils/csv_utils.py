"""Utility functions for CSV parsing and sampling."""

import polars as pl


def pick_representative_sample(df: pl.DataFrame, n: int = 3) -> list[dict]:
    """Return up to n rows that maximise non-null column coverage.

    Uses a greedy algorithm: repeatedly selects the row that adds the most
    newly-covered (non-null) columns, stopping when n rows are selected or
    all columns are covered.  Remaining slots are filled with sequential
    rows not yet selected.

    Args:
        df: Parsed Polars DataFrame.
        n:  Maximum number of rows to return.

    Returns:
        List of row dicts, sorted by original row index.
    """
    if df.is_empty():
        return []

    all_rows = df.to_dicts()
    n = min(n, len(all_rows))
    selected: list[int] = []
    uncovered = set(df.columns)

    while len(selected) < n and uncovered:
        best_idx, best_score = -1, -1
        for i, row in enumerate(all_rows):
            if i in selected:
                continue
            score = sum(1 for col in uncovered if row.get(col) is not None)
            if score > best_score:
                best_score, best_idx = score, i
        if best_idx == -1:
            break
        selected.append(best_idx)
        uncovered -= {col for col in uncovered if all_rows[best_idx].get(col) is not None}

    # Fill remaining slots with sequential rows not yet selected
    for i in range(len(all_rows)):
        if len(selected) >= n:
            break
        if i not in selected:
            selected.append(i)

    return [all_rows[i] for i in sorted(selected)]

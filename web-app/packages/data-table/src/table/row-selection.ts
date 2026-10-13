import type { RowSelectionState } from "@tanstack/react-table"

/**
 * The selection restricted to rows on screen. Selection never outlives its
 * rows: a page, filter, sort or search change that removes a row deselects
 * it, so a bulk action only ever touches rows the user can see.
 */
export function pruneSelection(
  selection: RowSelectionState,
  ids: Iterable<string>,
): RowSelectionState {
  const visible = new Set(ids)
  const kept = Object.keys(selection).filter(
    (id) => selection[id] && visible.has(id),
  )
  if (kept.length === Object.keys(selection).length) return selection
  return Object.fromEntries(kept.map((id) => [id, true]))
}

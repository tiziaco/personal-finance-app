"use client"

import { useEffect } from "react"
import type { DataTableState } from "./table-state"

/**
 * A server page past the end (its last row deleted, or a hand-edited ?page=)
 * comes back empty with the real total. Neither empty state is true then, nor
 * while that empty page stays on screen as placeholder data for the next one.
 * A settled one moves to the last page that has rows, without a Back entry.
 * Only a page beyond that one moves, so this cannot loop.
 *
 * Returns true while such a page is on screen: pass it to the table's
 * `isLoading` so it shows the skeleton instead of an empty state.
 */
export function useClampPage(
  {
    pageIndex,
    setPage,
  }: Pick<DataTableState<unknown>, "pageIndex" | "setPage">,
  {
    pageSize,
    total,
    rowCount,
    isPlaceholderData,
  }: {
    pageSize: number
    /** the server's total, undefined until the first page arrives */
    total: number | undefined
    /** rows on the page shown, undefined until the first page arrives */
    rowCount: number | undefined
    isPlaceholderData: boolean
  },
): boolean {
  const lastPageIndex = Math.ceil((total ?? 0) / pageSize) - 1
  const emptyPageOfMany = rowCount === 0 && (total ?? 0) > 0
  const pastTheEnd =
    emptyPageOfMany && !isPlaceholderData && pageIndex > lastPageIndex
  useEffect(() => {
    if (pastTheEnd) setPage(lastPageIndex, { history: "replace" })
  }, [pastTheEnd, lastPageIndex, setPage])
  return emptyPageOfMany
}

"use client"

import type { Table } from "@tanstack/react-table"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@app/ui/button"
import { labels } from "../labels"

/** 0-based page indexes to show, with "..." for gaps. */
export function getPageItems(
  currentPage: number,
  pageCount: number,
): Array<number | "..."> {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i)
  const items: Array<number | "..."> = [0]
  const start = Math.max(1, currentPage - 1)
  const end = Math.min(pageCount - 2, currentPage + 1)
  if (start > 1) items.push("...")
  for (let i = start; i <= end; i += 1) items.push(i)
  if (end < pageCount - 2) items.push("...")
  items.push(pageCount - 1)
  return items
}

export function DataTablePager<TData>({
  table,
  totalCount,
  disabled = false,
}: {
  table: Table<TData>
  totalCount: number
  disabled?: boolean
}) {
  "use no memo" // reads the mutable TanStack table instance
  const { pageIndex, pageSize } = table.getState().pagination
  const pageCount = Math.ceil(totalCount / pageSize)
  if (pageCount <= 1) return null

  const startItem = pageIndex * pageSize + 1
  const endItem = Math.min((pageIndex + 1) * pageSize, totalCount)

  return (
    <nav
      aria-label={labels.pagination}
      className="flex items-center justify-between border-t py-3"
    >
      <p className="hidden text-xs text-muted-foreground tabular-nums sm:block">
        {labels.pagerSummary(startItem, endItem, totalCount)}
      </p>
      <div className="flex flex-1 items-center justify-between gap-1 sm:justify-end">
        <Button
          variant="outline"
          size="icon-sm"
          aria-label={labels.previousPage}
          onClick={() => table.previousPage()}
          disabled={disabled || pageIndex === 0}
        >
          <ChevronLeft />
        </Button>
        {getPageItems(pageIndex, pageCount).map((item, idx) =>
          item === "..." ? (
            <span
              key={`gap-${idx}`}
              className="px-1 text-xs text-muted-foreground"
            >
              …
            </span>
          ) : (
            <Button
              key={item}
              variant={item === pageIndex ? "outline" : "ghost"}
              size="sm"
              className="tabular-nums"
              aria-current={item === pageIndex ? "page" : undefined}
              onClick={() => table.setPageIndex(item)}
              disabled={disabled}
            >
              {item + 1}
            </Button>
          ),
        )}
        <Button
          variant="outline"
          size="icon-sm"
          aria-label={labels.nextPage}
          onClick={() => table.nextPage()}
          disabled={disabled || pageIndex >= pageCount - 1}
        >
          <ChevronRight />
        </Button>
      </div>
    </nav>
  )
}

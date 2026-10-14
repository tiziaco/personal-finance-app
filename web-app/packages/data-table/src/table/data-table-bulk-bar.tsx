"use client"

import type { ReactNode } from "react"
import { X } from "lucide-react"
import { Button } from "@app/ui/button"
import { labels } from "../labels"

/**
 * A pill floating under the table: the count, the page's actions, Clear.
 * Sticky to the bottom of the scroll container, so on a long page it stays in
 * view over the rows. Rendered by DataTableCore while rows are selected.
 */
export function DataTableBulkBar({
  count,
  onClear,
  children,
}: {
  count: number
  onClear: () => void
  children?: ReactNode
}) {
  return (
    <div className="pointer-events-none sticky bottom-6 z-30 mt-3 flex justify-center">
      <div
        role="toolbar"
        aria-label={labels.bulkActions}
        className="pointer-events-auto flex animate-in items-center gap-3 rounded-xl border bg-card px-4 py-2 shadow-lg duration-200 fade-in slide-in-from-bottom-4"
      >
        <span className="sr-only">{labels.selectedCount(count)}</span>
        <span aria-hidden className="flex items-center gap-2">
          <span className="flex h-6 min-w-6 items-center justify-center rounded-lg bg-primary px-1.5 text-sm font-semibold text-primary-foreground tabular-nums">
            {count}
          </span>
          <span className="text-sm font-medium text-muted-foreground">
            {labels.selected}
          </span>
        </span>
        <div className="flex items-center gap-2">{children}</div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onClear}
          aria-label={labels.clearSelection}
        >
          <X />
        </Button>
      </div>
    </div>
  )
}

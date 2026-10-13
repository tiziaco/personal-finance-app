"use client"

import type { ReactNode } from "react"
import { X } from "lucide-react"
import { Button } from "@app/ui/button"
import { labels } from "../labels"

/** "N selected", the page's actions, and Clear. Rendered by DataTableCore while rows are selected. */
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
    <div
      role="toolbar"
      aria-label={labels.bulkActions}
      className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border bg-muted/50 px-3 py-1.5"
    >
      <span className="text-sm font-medium tabular-nums">
        {labels.selectedCount(count)}
      </span>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
      <Button
        variant="ghost"
        size="sm"
        className="ml-auto"
        onClick={onClear}
        aria-label={labels.clearSelection}
      >
        <X />
      </Button>
    </div>
  )
}

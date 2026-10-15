"use client"

import { useLayoutEffect, useRef, useState, type ReactNode } from "react"
import { X } from "lucide-react"
import { Button } from "@app/ui/button"
import { labels } from "../labels"

/**
 * A pill floating at the bottom of the viewport while rows are selected: the
 * count, the page's actions, Clear. Fixed, not sticky: the dashboard scrolls
 * the window, so a sticky bar would bind to a container that never scrolls.
 * It is centred on the box it sits in (the table's), measured, so it never
 * slides over the sidebar. The in-flow spacer lets the page scroll past it.
 * Rendered by DataTableCore after the pager.
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
  const spacer = useRef<HTMLDivElement>(null)
  const [centre, setCentre] = useState<number | null>(null)
  useLayoutEffect(() => {
    const box = spacer.current?.parentElement
    if (!box) return
    const measure = () => {
      const r = box.getBoundingClientRect()
      setCentre(r.left + r.width / 2)
    }
    measure()
    window.addEventListener("resize", measure)
    // The sidebar collapsing moves and resizes the box without resizing the window.
    const observer = new ResizeObserver(measure)
    observer.observe(box)
    return () => {
      window.removeEventListener("resize", measure)
      observer.disconnect()
    }
  }, [])

  return (
    <div ref={spacer} className="h-16">
      <div
        className="fixed bottom-6 z-30 -translate-x-1/2"
        style={{ left: centre ?? "50%" }}
      >
        <div
          role="toolbar"
          aria-label={labels.bulkActions}
          className="flex animate-in items-center gap-3 rounded-xl border bg-card px-4 py-2 shadow-lg duration-200 fade-in slide-in-from-bottom-4"
        >
          <span className="sr-only">{labels.selectedCount(count)}</span>
          <span aria-hidden className="flex items-center gap-2">
            <span className="flex h-6 min-w-6 items-center justify-center rounded-lg bg-primary px-1.5 text-sm font-semibold text-primary-foreground tabular-nums">
              {count}
            </span>
            <span className="text-sm font-medium whitespace-nowrap text-muted-foreground">
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
    </div>
  )
}

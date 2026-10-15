"use client"

import { X } from "lucide-react"
import { labels } from "../labels"

export function FilterChip({
  label,
  onRemove,
}: {
  label: string
  onRemove: () => void
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border bg-muted px-2 py-0.5 text-xs font-medium">
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={labels.removeFilter(label)}
        className="rounded-sm p-0.5 text-muted-foreground hover:bg-background hover:text-foreground"
      >
        <X className="size-3" />
      </button>
    </span>
  )
}

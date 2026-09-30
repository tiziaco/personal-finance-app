"use client"

import type { ComponentProps, ReactNode } from "react"
import { ListFilter } from "lucide-react"
import { Button } from "@app/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@app/ui/popover"
import { cn } from "@app/core/lib/utils"
import { labels } from "../labels"

/**
 * Popover shell for a list's filters. The fields inside are per list and
 * read/write only through `filters` / `setFilters`: no local state.
 */
export function FilterPanel({
  activeCount,
  onClearAll,
  label = labels.filters,
  children,
  className,
}: {
  activeCount: number
  onClearAll: () => void
  label?: string
  children: ReactNode
  className?: string
}) {
  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            className={cn(activeCount > 0 && "border-primary text-primary")}
          />
        }
      >
        <ListFilter />
        {label}
        {activeCount > 0 && (
          <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground tabular-nums">
            {activeCount}
            <span className="sr-only"> {labels.activeFilters}</span>
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" aria-label={label} className={className}>
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium">{label}</p>
          {activeCount > 0 && (
            <Button variant="ghost" size="sm" onClick={onClearAll}>
              {labels.clearAll}
            </Button>
          )}
        </div>
        {children}
      </PopoverContent>
    </Popover>
  )
}

export function FilterField({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor: string
  children: ReactNode
}) {
  return (
    <div className="space-y-1">
      <label
        htmlFor={htmlFor}
        className="text-xs font-medium text-muted-foreground"
      >
        {label}
      </label>
      {children}
    </div>
  )
}

/**
 * Native select styled like `@app/ui/input`. Native because "" (no filter) is
 * a valid value, which the Base UI Select does not model.
 */
export function FilterSelect({
  className,
  ...props
}: ComponentProps<"select">) {
  return (
    <select
      className={cn(
        "h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30",
        className,
      )}
      {...props}
    />
  )
}

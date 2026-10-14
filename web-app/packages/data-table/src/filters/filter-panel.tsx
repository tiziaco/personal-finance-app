"use client"

import type { ComponentProps, ReactNode } from "react"
import { ListFilter } from "lucide-react"
import { Button } from "@app/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@app/ui/sheet"
import { cn } from "@app/core/lib/utils"
import { labels } from "../labels"

/** The title style every filter section shares. */
export const FILTER_SECTION_TITLE =
  "text-xs font-semibold tracking-wider text-muted-foreground uppercase"

/**
 * A right-hand sheet for a list's filters; full width on a phone. Each child
 * is one ruled section. The fields inside are per list and read/write only
 * through `filters` / `setFilters`: no local state.
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
    <Sheet>
      <SheetTrigger
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
      </SheetTrigger>
      <SheetContent
        side="right"
        className={cn("gap-0 data-[side=right]:w-full", className)}
      >
        <SheetHeader className="border-b pr-12">
          <SheetTitle>{label}</SheetTitle>
          {activeCount > 0 && (
            <SheetDescription className="text-xs">
              {labels.activeCount(activeCount)}
            </SheetDescription>
          )}
        </SheetHeader>
        <div className="flex-1 divide-y overflow-y-auto px-4 *:py-5">
          {children}
        </div>
        {activeCount > 0 && (
          <SheetFooter className="border-t">
            <Button variant="outline" className="w-full" onClick={onClearAll}>
              {labels.clearAll}
            </Button>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  )
}

/** One labelled input: a section of its own, or a field inside a FilterSection. */
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
    <div className="space-y-2">
      <label htmlFor={htmlFor} className={cn("block", FILTER_SECTION_TITLE)}>
        {label}
      </label>
      {children}
    </div>
  )
}

/** A section holding several inputs under one title (e.g. a min and a max). */
export function FilterSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <fieldset className="space-y-2">
      <legend className={cn("mb-2", FILTER_SECTION_TITLE)}>{title}</legend>
      {children}
    </fieldset>
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

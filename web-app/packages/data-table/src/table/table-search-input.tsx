"use client"

import { Search } from "lucide-react"
import { Input } from "@app/ui/input"
import { cn } from "@app/core/lib/utils"
import { labels } from "../labels"

export function TableSearchInput({
  value,
  onChange,
  placeholder = labels.search,
  className,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}) {
  return (
    <div className={cn("relative w-full sm:w-64", className)}>
      <Search
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="pl-8"
      />
    </div>
  )
}

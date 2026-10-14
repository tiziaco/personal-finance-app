"use client"

import type { Category, CategoryResponse } from "@app/api-client/types"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@app/ui/select"

/** Pick one category; empty until the user picks. Label it with `<Label htmlFor={id}>`. */
export function CategorySelect({
  id,
  value,
  onChange,
  categories,
}: {
  id: string
  value: Category | ""
  onChange: (category: Category) => void
  categories: CategoryResponse[]
}) {
  return (
    <Select
      items={categories}
      value={value || null}
      onValueChange={(next) => next && onChange(next as Category)}
    >
      <SelectTrigger id={id} className="w-full">
        <SelectValue placeholder="Pick a category" />
      </SelectTrigger>
      <SelectContent>
        {categories.map((c) => (
          <SelectItem key={c.value} value={c.value}>
            {c.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

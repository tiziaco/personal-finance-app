"use client"

import { ChevronDownIcon } from "lucide-react"
import type { Category, CategoryResponse } from "@app/api-client/types"
import { cn } from "@app/core/lib/utils"
import { badgeVariants } from "@app/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@app/ui/dropdown-menu"

/** A transaction's category as a chip; clicking it picks another. */
export function CategoryPicker({
  value,
  onChange,
  categories,
  label,
}: {
  value: Category
  onChange: (category: Category) => void
  categories: CategoryResponse[]
  label: (slug: string) => string
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(badgeVariants({ variant: "outline" }), "cursor-pointer")}
      >
        {label(value)}
        <ChevronDownIcon data-icon="inline-end" />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-auto">
        <DropdownMenuRadioGroup
          value={value}
          onValueChange={(next: Category) => {
            if (next !== value) onChange(next)
          }}
        >
          {categories.map((c) => (
            // A radio item keeps the menu open by default; a pick closes it.
            <DropdownMenuRadioItem key={c.value} value={c.value} closeOnClick>
              {c.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

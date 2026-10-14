"use client"

import type { Table } from "@tanstack/react-table"
import { ChevronDown } from "lucide-react"
import { Button } from "@app/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@app/ui/dropdown-menu"
import { labels } from "../labels"

export function DataTableColumnToggle<TData>({
  table,
}: {
  table: Table<TData>
}) {
  "use no memo" // reads the mutable TanStack table instance
  const columns = table
    .getAllLeafColumns()
    .filter(
      (column) =>
        typeof column.accessorFn !== "undefined" && column.getCanHide(),
    )

  // Base UI checkbox items keep the menu open (closeOnClick defaults to false),
  // so several columns can be toggled in one visit.
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="outline" />}>
        {labels.columns}
        <ChevronDown />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {columns.map((column) => {
          const header = column.columnDef.header
          return (
            <DropdownMenuCheckboxItem
              key={column.id}
              checked={column.getIsVisible()}
              onCheckedChange={(checked) => column.toggleVisibility(checked)}
            >
              {typeof header === "string" ? header : column.id}
            </DropdownMenuCheckboxItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

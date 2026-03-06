"use client"

import { Table } from "@tanstack/react-table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { X } from "lucide-react"

export interface BulkAction<TData> {
  label: string
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link"
  onClick?: (selectedRows: TData[], resetSelection: () => void) => void
  icon?: React.ReactNode
}

interface DataTableBulkActionsProps<TData> {
  table: Table<TData>
  actions: BulkAction<TData>[]
}

export function DataTableBulkActions<TData>({
  table,
  actions,
}: DataTableBulkActionsProps<TData>) {
  const selectedRows = table.getFilteredSelectedRowModel().rows
  const selectedCount = selectedRows.length

  if (selectedCount === 0) {
    return null
  }

  const selectedData = selectedRows.map((row) => row.original)

  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 animate-in fade-in slide-in-from-bottom-4 duration-200">
      <div className="flex items-center gap-3 rounded-xl border bg-background/95 px-4 py-2 shadow-lg backdrop-blur supports-backdrop-filter:bg-background/80">
        {/* Selected count badge */}
        <div className="flex items-center gap-2">
          <Badge className="h-6 w-6 rounded-lg p-0 flex items-center justify-center text-sm font-semibold">
            {selectedCount}
          </Badge>
          <span className="text-sm font-medium text-muted-foreground">selected</span>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {actions.map((action, index) => {
            const resetSelection = () => table.resetRowSelection()
            
            return (
              <Button
                key={index}
                variant={action.variant || "default"}
                size="sm"
                onClick={() => action.onClick?.(selectedData, resetSelection)}
                className="h-9"
              >
                {action.icon && <span className="mr-2">{action.icon}</span>}
                {action.label}
              </Button>
            )
          })}
        </div>

        {/* Clear selection button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => table.resetRowSelection()}
          className="h-9 w-9 p-0"
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Clear selection</span>
        </Button>
      </div>
    </div>
  )
}

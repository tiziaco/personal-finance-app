'use client'

import { useState, useRef, useEffect } from 'react'
import {
  createColumnHelper,
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  flexRender,
  type RowSelectionState,
} from '@tanstack/react-table'
import { ChevronLeft, ChevronRight, Edit2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DataTableBulkActions } from '@/components/ui/data-table-bulk-actions'
import { TableSkeleton } from '@/components/shared/skeletons/table-skeleton'
import { type TransactionResponse } from '@/types/transaction'
import { formatCurrency, formatDate } from '@/lib/format'

export interface TransactionsTableProps {
  data: TransactionResponse[]
  total: number
  offset: number
  limit: number
  page: number
  onPageChange: (page: number) => void
  onEditTransaction: (transaction: TransactionResponse) => void
  onBulkRecategorize: (transactions: TransactionResponse[], resetSelection: () => void) => void
  isLoading?: boolean
}

const columnHelper = createColumnHelper<TransactionResponse>()

export function TransactionsTable({
  data,
  total,
  offset,
  limit,
  page,
  onPageChange,
  onEditTransaction,
  onBulkRecategorize,
  isLoading,
}: TransactionsTableProps) {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const selectAllRef = useRef<HTMLInputElement>(null)

  const columns = [
    // 1. Select column
    columnHelper.display({
      id: 'select',
      header: ({ table }) => (
        <input
          type="checkbox"
          ref={selectAllRef}
          checked={table.getIsAllRowsSelected()}
          onChange={table.getToggleAllRowsSelectedHandler()}
          aria-label="Select all rows"
          className="cursor-pointer"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
          aria-label="Select row"
          className="cursor-pointer"
        />
      ),
    }),
    // 2. Date column
    columnHelper.accessor('date', {
      header: 'Date',
      cell: (info) => formatDate(info.getValue()),
    }),
    // 3. Merchant column
    columnHelper.accessor('merchant', {
      header: 'Merchant',
      cell: (info) => (
        <span className="block max-w-[200px] truncate">{info.getValue()}</span>
      ),
    }),
    // 4. Amount column
    columnHelper.accessor('amount', {
      header: 'Amount',
      cell: (info) => formatCurrency(info.getValue()),
    }),
    // 5. Category column
    columnHelper.accessor('category', {
      header: 'Category',
      cell: (info) => (
        <span
          className="text-sm cursor-pointer hover:underline"
          onClick={() => onEditTransaction(info.row.original)}
        >
          {info.getValue()}
        </span>
      ),
    }),
    // 6. Confidence score column
    columnHelper.accessor('confidence_score', {
      header: 'Confidence',
      cell: (info) => {
        const score = info.getValue()
        const pct = `${(score * 100).toFixed(0)}%`
        return (
          <span className={score < 0.7 ? 'text-amber-600' : 'text-green-600'}>{pct}</span>
        )
      },
    }),
    // 7. Actions column
    columnHelper.display({
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onEditTransaction(row.original)}
          aria-label="Edit transaction"
        >
          <Edit2 className="h-4 w-4" />
        </Button>
      ),
    }),
  ]

  const table = useReactTable({
    data,
    columns,
    state: { rowSelection },
    onRowSelectionChange: setRowSelection,
    enableRowSelection: true,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getRowId: (row) => String(row.id),
    // NO getPaginationRowModel — pagination is server-side
  })

  // Keep the select-all checkbox indeterminate state in sync
  useEffect(() => {
    if (selectAllRef.current) {
      const someSelected = table.getIsSomeRowsSelected()
      selectAllRef.current.indeterminate = someSelected
    }
  }, [table, rowSelection])

  // Pagination calculations
  const totalPages = Math.ceil(total / limit)
  const from = offset + 1
  const to = Math.min(offset + limit, total)

  if (isLoading) {
    return <TableSkeleton rows={25} columns={7} />
  }

  return (
    <>
      <div className="w-full overflow-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/50"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-t hover:bg-muted/30 transition-colors">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-3">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
            {table.getRowModel().rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                  No transactions found.
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {/* Pagination controls */}
        <div className="flex items-center justify-between px-2 py-3">
          <span className="text-sm text-muted-foreground">
            Showing {total > 0 ? from : 0}–{to} of {total} transactions
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page === 0}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <span className="text-sm">
              Page {page + 1} of {totalPages || 1}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page + 1)}
              disabled={to >= total}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* Bulk actions — outside table wrapper so it sticks to viewport bottom */}
      <DataTableBulkActions
        table={table}
        actions={[
          {
            label: 'Recategorize',
            onClick: (selectedRows, resetSelection) => {
              onBulkRecategorize(selectedRows, resetSelection)
            },
          },
        ]}
      />
    </>
  )
}

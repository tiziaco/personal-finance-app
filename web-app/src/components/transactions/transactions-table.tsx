'use client'

import { useState } from 'react'
import {
  createColumnHelper,
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  flexRender,
  type RowSelectionState,
} from '@tanstack/react-table'
import { ChevronLeft, ChevronRight, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { Checkbox } from '@/components/ui/checkbox'
import { useSidebar } from '@/components/ui/sidebar'
import { DataTableBulkActions } from '@/components/ui/data-table-bulk-actions'
import { TableSkeleton } from '@/components/shared/skeletons/table-skeleton'
import { type TransactionResponse } from '@/types/transaction'
import { useFormatCurrency } from '@/hooks/use-currency-format'
import { useFormatDate } from '@/hooks/use-date-format'
import { useCurrency } from '@/providers/currency-provider'

function TransactionCard({
  transaction,
  onEditTransaction,
  onDelete,
}: {
  transaction: TransactionResponse
  onEditTransaction: (t: TransactionResponse) => void
  onDelete: (t: TransactionResponse) => void
}) {
  const formatDate = useFormatDate()
  const { formatAmount } = useCurrency()

  return (
    <div className="rounded-lg border bg-card p-4 flex items-start justify-between gap-3">
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-medium text-sm truncate">{transaction.merchant}</p>
        <p className="text-xs text-muted-foreground">{formatDate(transaction.date)}</p>
        <span className="inline-block text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
          {transaction.category}
        </span>
      </div>
      <div className="shrink-0 flex flex-col items-end gap-2">
        <p className="font-semibold text-sm">{formatAmount(transaction.amount)}</p>
        <DropdownMenu>
          <DropdownMenuTrigger
            className="min-h-12 min-w-12 flex items-center justify-center rounded-md hover:bg-muted"
            aria-label="Transaction actions"
          >
            <MoreHorizontal className="h-4 w-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onEditTransaction(transaction)}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => onDelete(transaction)}
              className="text-destructive focus:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}

export interface TransactionsTableProps {
  data: TransactionResponse[]
  total: number
  offset: number
  limit: number
  page: number
  onPageChange: (page: number) => void
  onEditCategory: (transaction: TransactionResponse) => void
  onEditTransaction: (transaction: TransactionResponse) => void
  onDeleteTransaction: (transaction: TransactionResponse) => void
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
  onEditCategory,
  onEditTransaction,
  onDeleteTransaction,
  onBulkRecategorize,
  isLoading,
}: TransactionsTableProps) {
  const formatDate = useFormatDate()
  const formatCurrency = useFormatCurrency()
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const { state: sidebarState, isMobile } = useSidebar()
  const bulkActionsLeft = isMobile
    ? '50%'
    : sidebarState === 'expanded'
      ? 'calc((100vw + var(--sidebar-width)) / 2)'
      : 'calc((100vw + var(--sidebar-width-icon)) / 2)'

  const columns = [
    // 1. Select column
    columnHelper.display({
      id: 'select',
      header: ({ table }) => (
        <div className="flex items-center justify-center w-8">
          <Checkbox
            checked={table.getIsAllRowsSelected()}
            indeterminate={table.getIsSomeRowsSelected()}
            onCheckedChange={(checked) => table.toggleAllRowsSelected(!!checked)}
            aria-label="Select all rows"
          />
        </div>
      ),
      cell: ({ row }) => (
        <div className="flex items-center justify-center w-8">
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(checked) => row.toggleSelected(!!checked)}
            aria-label="Select row"
          />
        </div>
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
        <span className="block max-w-50 truncate">{info.getValue()}</span>
      ),
    }),
    // 4. Amount column
    columnHelper.accessor('amount', {
      header: 'Amount',
      cell: (info) => {
        const val = Number(info.getValue())
        return (
          <span className={cn('font-medium tabular-nums', val < 0 ? 'text-destructive' : 'text-success')}>
            {formatCurrency(val)}
          </span>
        )
      },
    }),
    // 5. Category column
    columnHelper.accessor('category', {
      header: 'Category',
      cell: (info) => (
        <span
          className="inline-block text-xs px-2 py-0.5 rounded-md bg-muted text-muted-foreground cursor-pointer hover:bg-muted/70 transition-colors"
          onClick={() => onEditCategory(info.row.original)}
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
          <span className={score < 0.7 ? 'text-warning' : 'text-success'}>{pct}</span>
        )
      },
    }),
    // 7. Actions column
    columnHelper.display({
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <DropdownMenu>
          <DropdownMenuTrigger
            className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-muted"
            aria-label="Transaction actions"
          >
            <MoreHorizontal className="h-4 w-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onEditTransaction(row.original)}>
              <Pencil className="h-4 w-4 mr-2" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => onDeleteTransaction(row.original)}
              className="text-destructive focus:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
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

  // Pagination calculations
  const totalPages = Math.ceil(total / limit)
  const from = offset + 1
  const to = Math.min(offset + limit, total)

  if (isLoading) {
    return <TableSkeleton rows={25} columns={7} />
  }

  return (
    <>
      {/* === DESKTOP TABLE: hidden on mobile (< sm = 640px) === */}
      <div className="hidden sm:block w-full overflow-auto rounded-xl border border-border/60 bg-card shadow-sm">
        <table className="w-full text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-2 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/40"
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
              <tr key={row.id} className="border-t hover:bg-muted/20 transition-colors">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-2">
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
      </div>

      {/* === MOBILE CARD LIST: shown only on mobile (< sm) === */}
      <div className="sm:hidden space-y-3">
        {table.getRowModel().rows.length === 0 ? (
          <p className="text-center text-muted-foreground py-8">No transactions found.</p>
        ) : (
          table.getRowModel().rows.map((row) => (
            <TransactionCard
              key={row.id}
              transaction={row.original}
              onEditTransaction={onEditTransaction}
              onDelete={onDeleteTransaction}
            />
          ))
        )}
      </div>

      {/* === PAGINATION: visible on all breakpoints === */}
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

      {/* Bulk actions — outside table wrapper so it sticks to viewport bottom */}
      <DataTableBulkActions
        table={table}
        style={{ left: bulkActionsLeft }}
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

"use client"

import * as React from "react"
import {
  flexRender,
  getCoreRowModel,
  getExpandedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type ColumnMeta,
  type ExpandedState,
  type FilterFn,
  type OnChangeFn,
  type PaginationState,
  type Row,
  type RowSelectionState,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table"
import { rankItem } from "@tanstack/match-sorter-utils"
import { ChevronDown, ChevronRight } from "lucide-react"
import { Button } from "@app/ui/button"
import { Checkbox } from "@app/ui/checkbox"
import { Skeleton } from "@app/ui/skeleton"
import {
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@app/ui/table"
import { useIsMobile } from "@app/ui/hooks/use-mobile"
import { cn } from "@app/core/lib/utils"
import { labels } from "../labels"
import "./column-meta"
import { DataTableBulkBar } from "./data-table-bulk-bar"
import { DataTableColumnToggle } from "./data-table-column-toggle"
import { DataTablePager } from "./data-table-pager"
import { pruneSelection } from "./row-selection"
import { TableSearchInput } from "./table-search-input"
import type { ServerTableControls } from "./table-state"

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const fuzzyFilter: FilterFn<any> = (row, columnId, value, addMeta) => {
  const itemRank = rankItem(row.getValue(columnId), value)
  addMeta({ itemRank })
  return itemRank.passed
}

export interface ColumnFreezing {
  left?: number
  right?: number
}

type FreezeInfo =
  { frozen: false } | { frozen: true; side: "left" | "right"; offset: number }
const NOT_FROZEN: FreezeInfo = { frozen: false }
const SKELETON_ROWS = 5

/** Sticky offset for a visible column. Assumes a single header row. */
export function getColumnFreezeInfo(
  index: number,
  columnIds: string[],
  widths: Record<string, number>,
  freeze: ColumnFreezing,
): FreezeInfo {
  const left = freeze.left ?? 0
  const right = freeze.right ?? 0
  if (index < left) {
    let offset = 0
    for (let i = 0; i < index; i++) offset += widths[columnIds[i]] ?? 0
    return { frozen: true, side: "left", offset }
  }
  if (right > 0 && index >= columnIds.length - right) {
    let offset = 0
    for (let i = columnIds.length - 1; i > index; i--)
      offset += widths[columnIds[i]] ?? 0
    return { frozen: true, side: "right", offset }
  }
  return NOT_FROZEN
}

function freezeStyle(info: FreezeInfo): React.CSSProperties | undefined {
  if (!info.frozen) return undefined
  return { position: "sticky", [info.side]: info.offset }
}

function widthStyle<TData, TValue>(
  meta?: ColumnMeta<TData, TValue>,
): React.CSSProperties | undefined {
  return meta?.width
    ? { width: meta.width, minWidth: meta.width, maxWidth: meta.width }
    : undefined
}

function defaultGetRowId(
  original: unknown,
  index: number,
  parent?: { id: string },
): string {
  const id = (original as { id?: unknown } | null)?.id
  if (id != null) return parent ? `${parent.id}.${String(id)}` : String(id)
  return parent ? `${parent.id}.${index}` : String(index)
}

export interface DataTableBaseProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  title?: string
  /** right-aligned in the header row (e.g. a "New" button) */
  headerActions?: React.ReactNode
  /** controls next to the search: search input, filter panel */
  toolbar?: React.ReactNode
  /** row under the toolbar: filter chips */
  belowToolbar?: React.ReactNode
  /** adds an expander column; the returned node renders under the row */
  renderSubComponent?: (row: Row<TData>) => React.ReactNode
  /** nested rows, expandable in place (use row.depth / row.getCanExpand in cells) */
  getSubRows?: (originalRow: TData, index: number) => TData[] | undefined
  /** a leading checkbox column; selection holds only rows on screen */
  enableRowSelection?: boolean
  /** the bulk bar's actions, shown while rows are selected */
  renderBulkActions?: (
    selected: TData[],
    clearSelection: () => void,
  ) => React.ReactNode
  /** below 768px the body is a list of these cards; toolbar, chips and pager stay */
  renderCard?: (row: Row<TData>) => React.ReactNode
  showFooter?: boolean
  showColumnToggle?: boolean
  /** uncontrolled initial visibility, e.g. { internal_notes: false } */
  defaultColumnVisibility?: VisibilityState
  /** controlled visibility; pair with onColumnVisibilityChange to persist it */
  columnVisibility?: VisibilityState
  onColumnVisibilityChange?: (visibility: VisibilityState) => void
  /** let multi-word headers wrap */
  allowHeaderWrapping?: boolean
  noDataMessage?: React.ReactNode
  /** first load, no rows yet: skeleton rows instead of noDataMessage */
  isLoading?: boolean
  /** when set, shown in the body instead of rows */
  errorMessage?: React.ReactNode
  getRowClassName?: (row: Row<TData>) => string | undefined
  onRowClick?: (row: Row<TData>, event: React.MouseEvent) => void
  /** defaults to `row.id`, falling back to the index */
  getRowId?: (originalRow: TData, index: number, parent?: Row<TData>) => string
  /** px; enables a scrolling body with a sticky header */
  maxScrollHeight?: number
  freezeColumns?: ColumnFreezing
  density?: "default" | "compact"
  className?: string
}

export type DataTableMode =
  | {
      kind: "client"
      pageSize: number
      search?: {
        value: string
        onChange: (value: string) => void
        placeholder: string
      }
    }
  | { kind: "server"; controls: ServerTableControls }

export interface DataTableCoreProps<TData, TValue> extends DataTableBaseProps<
  TData,
  TValue
> {
  mode: DataTableMode
  /** stale rows on screen while the next page loads: dims them, disables the pager */
  isPending?: boolean
}

/**
 * The one table body. Internal: feature code renders ClientDataTable or
 * ServerDataTable. A new table feature goes here behind an optional prop,
 * never into a third table component.
 */
export function DataTableCore<TData, TValue>({
  columns,
  data,
  title,
  headerActions,
  toolbar,
  belowToolbar,
  renderSubComponent,
  getSubRows,
  enableRowSelection = false,
  renderBulkActions,
  renderCard,
  showFooter = false,
  showColumnToggle = false,
  defaultColumnVisibility,
  columnVisibility,
  onColumnVisibilityChange,
  allowHeaderWrapping = false,
  noDataMessage = labels.noResults,
  isLoading = false,
  errorMessage,
  getRowClassName,
  onRowClick,
  getRowId,
  maxScrollHeight,
  freezeColumns,
  density = "default",
  className,
  mode,
  isPending = false,
}: DataTableCoreProps<TData, TValue>) {
  "use no memo" // reads the mutable TanStack table instance
  const isServer = mode.kind === "server"
  const isMobile = useIsMobile()
  const asCards = Boolean(renderCard) && isMobile
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [pagination, setPagination] = React.useState<PaginationState>({
    pageIndex: 0,
    pageSize: mode.kind === "client" ? mode.pageSize : 10,
  })
  const [expanded, setExpanded] = React.useState<ExpandedState>({})
  const [rowSelection, setRowSelection] = React.useState<RowSelectionState>({})
  const rowIdOf = getRowId ?? defaultGetRowId
  const selection = enableRowSelection
    ? pruneSelection(
        rowSelection,
        data.map((row, i) => rowIdOf(row, i)),
      )
    : {}
  // Commit the prune to state (adjust-state-during-render): a row that leaves
  // the screen stays deselected if it comes back. Loop-free: pruneSelection
  // returns the same object once nothing is left to drop.
  if (enableRowSelection && selection !== rowSelection)
    setRowSelection(selection)
  const selectedCount = Object.keys(selection).length
  const handleSelectionChange: OnChangeFn<RowSelectionState> = (updater) =>
    setRowSelection(
      typeof updater === "function" ? updater(selection) : updater,
    )
  const [localVisibility, setLocalVisibility] = React.useState<VisibilityState>(
    columnVisibility ?? defaultColumnVisibility ?? {},
  )
  const visibility = columnVisibility ?? localVisibility

  const handleVisibilityChange: OnChangeFn<VisibilityState> = (updater) => {
    const next = typeof updater === "function" ? updater(visibility) : updater
    if (columnVisibility === undefined) setLocalVisibility(next)
    onColumnVisibilityChange?.(next)
  }

  const cols = React.useMemo<ColumnDef<TData, TValue>[]>(() => {
    const selectColumn: ColumnDef<TData, TValue> = {
      id: "select",
      enableSorting: false,
      enableHiding: false,
      meta: { width: "2.5rem" },
      header: ({ table }) => (
        <Checkbox
          aria-label={labels.selectAllOnPage}
          checked={table.getIsAllPageRowsSelected()}
          indeterminate={table.getIsSomePageRowsSelected()}
          onCheckedChange={(checked) =>
            table.toggleAllPageRowsSelected(checked)
          }
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          aria-label={labels.selectRow}
          checked={row.getIsSelected()}
          onCheckedChange={(checked) => row.toggleSelected(checked)}
          onClick={(event) => event.stopPropagation()}
        />
      ),
    }
    const base: ColumnDef<TData, TValue>[] = renderSubComponent
      ? [
          {
            id: "expander",
            header: "",
            enableSorting: false,
            enableHiding: false,
            meta: { width: "3rem" },
            cell: ({ row }) => (
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={
                  row.getIsExpanded() ? labels.collapseRow : labels.expandRow
                }
                aria-expanded={row.getIsExpanded()}
                onClick={(event) => {
                  event.stopPropagation()
                  row.toggleExpanded()
                }}
              >
                <ChevronRight
                  className={cn(
                    "size-4 transition",
                    row.getIsExpanded() && "rotate-90",
                  )}
                />
              </Button>
            ),
          },
          ...columns,
        ]
      : columns
    return enableRowSelection ? [selectColumn, ...base] : base
  }, [columns, renderSubComponent, enableRowSelection])

  const globalFilter =
    mode.kind === "client" ? (mode.search?.value ?? "") : undefined

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table returns a mutable instance; this component opts out of React Compiler
  const table = useReactTable<TData>({
    data,
    columns: cols,
    getRowId: getRowId ?? defaultGetRowId,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    getSubRows,
    enableMultiSort: false,
    sortDescFirst: false,
    getRowCanExpand: renderSubComponent ? () => true : undefined,
    enableRowSelection,
    onRowSelectionChange: handleSelectionChange,
    onExpandedChange: setExpanded,
    onColumnVisibilityChange: handleVisibilityChange,
    ...(mode.kind === "server"
      ? {
          manualSorting: true,
          manualFiltering: true,
          manualPagination: true,
          rowCount: mode.controls.totalCount,
          onSortingChange: mode.controls.onSortingChange,
          onPaginationChange: mode.controls.onPaginationChange,
        }
      : {
          getSortedRowModel: getSortedRowModel(),
          getFilteredRowModel: getFilteredRowModel(),
          getPaginationRowModel: getPaginationRowModel(),
          globalFilterFn: fuzzyFilter,
          onSortingChange: setSorting,
          onPaginationChange: setPagination,
        }),
    state: {
      sorting: mode.kind === "server" ? mode.controls.sorting : sorting,
      pagination:
        mode.kind === "server" ? mode.controls.pagination : pagination,
      globalFilter,
      columnVisibility: visibility,
      expanded,
      rowSelection: selection,
    },
  })

  // Frozen columns need real widths for their sticky offsets.
  const tableRef = React.useRef<HTMLTableElement>(null)
  const [widths, setWidths] = React.useState<Record<string, number>>({})
  const hasFrozen =
    (freezeColumns?.left ?? 0) > 0 || (freezeColumns?.right ?? 0) > 0
  const columnIds = table.getVisibleLeafColumns().map((c) => c.id)
  const columnKey = columnIds.join("|")
  React.useLayoutEffect(() => {
    const thead = tableRef.current?.tHead
    if (!hasFrozen || !thead) return
    // Direct children only: a renderSubComponent may nest another table.
    const ths = thead.querySelectorAll<HTMLElement>(
      ":scope > tr > th[data-column-id]",
    )
    const measure = () => {
      const next: Record<string, number> = {}
      ths.forEach((th) => {
        next[th.dataset.columnId!] = th.offsetWidth
      })
      setWidths(next)
    }
    measure()
    const observer = new ResizeObserver(measure)
    ths.forEach((th) => observer.observe(th))
    return () => observer.disconnect()
  }, [hasFrozen, columnKey])

  const freezeInfo = hasFrozen
    ? columnIds.map((_, i) =>
        getColumnFreezeInfo(i, columnIds, widths, freezeColumns ?? {}),
      )
    : []
  const colSpan = columnIds.length
  const rows = table.getRowModel().rows
  const search = mode.kind === "client" ? mode.search : undefined
  const hasHeader = Boolean(
    title || search || toolbar || showColumnToggle || headerActions,
  )

  return (
    <div className={className}>
      {(hasHeader || belowToolbar) && (
        <div className="mb-2 space-y-2">
          {hasHeader && (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                {title && <h2 className="text-lg font-semibold">{title}</h2>}
                {search && (
                  <TableSearchInput
                    value={search.value}
                    onChange={search.onChange}
                    placeholder={search.placeholder}
                  />
                )}
                {toolbar}
                {showColumnToggle && <DataTableColumnToggle table={table} />}
              </div>
              {headerActions && (
                <div className="flex items-center gap-2">{headerActions}</div>
              )}
            </div>
          )}
          {belowToolbar && (
            <div className="flex min-h-7 flex-wrap items-center gap-2">
              {belowToolbar}
            </div>
          )}
        </div>
      )}

      {!asCards && enableRowSelection && selectedCount > 0 && (
        <DataTableBulkBar
          count={selectedCount}
          onClear={() => setRowSelection({})}
        >
          {renderBulkActions?.(
            table.getSelectedRowModel().rows.map((r) => r.original),
            () => setRowSelection({}),
          )}
        </DataTableBulkBar>
      )}

      {asCards ? (
        <ul
          className={cn(
            "space-y-2",
            isPending && "opacity-60 transition-opacity",
          )}
          aria-busy={isPending || undefined}
        >
          {errorMessage != null ? (
            <li role="alert" className="py-6 text-center text-destructive">
              {errorMessage}
            </li>
          ) : isLoading ? (
            Array.from({ length: SKELETON_ROWS }, (_, i) => (
              <li key={i}>
                <Skeleton className="h-16 w-full" />
              </li>
            ))
          ) : rows.length === 0 ? (
            <li className="py-6 text-center text-muted-foreground">
              {noDataMessage}
            </li>
          ) : (
            rows.map((row) => <li key={row.id}>{renderCard!(row)}</li>)
          )}
        </ul>
      ) : (
        <div
          data-slot="table-container"
          className={cn(
            "relative w-full overflow-x-auto",
            hasFrozen && "overflow-y-clip",
            maxScrollHeight && "overflow-y-auto",
          )}
          style={maxScrollHeight ? { maxHeight: maxScrollHeight } : undefined}
        >
          <table
            ref={tableRef}
            data-slot="table"
            aria-busy={isPending || undefined}
            className={cn(
              "w-full caption-bottom text-xs",
              hasFrozen && "border-separate border-spacing-0",
            )}
          >
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} className="hover:bg-transparent">
                  {headerGroup.headers.map((header, index) => {
                    const def = header.column.columnDef
                    const meta = def.meta
                    const freeze = freezeInfo[index] ?? NOT_FROZEN
                    const canSort =
                      header.column.getCanSort() && Boolean(def.header)
                    const sorted = header.column.getIsSorted()
                    const text =
                      typeof def.header === "string" ? def.header.trim() : ""
                    const wraps = allowHeaderWrapping && /\s/.test(text)
                    return (
                      <TableHead
                        key={header.id}
                        colSpan={header.colSpan}
                        data-column-id={header.column.id}
                        aria-sort={
                          canSort
                            ? sorted === "asc"
                              ? "ascending"
                              : sorted === "desc"
                                ? "descending"
                                : "none"
                            : undefined
                        }
                        style={{ ...widthStyle(meta), ...freezeStyle(freeze) }}
                        className={cn(
                          density === "compact" && "h-8 px-2 text-xs",
                          wraps && "whitespace-normal",
                          meta?.align === "right" && "text-right",
                          hasFrozen && "border-b",
                          maxScrollHeight && "sticky top-0 z-10 bg-background",
                          freeze.frozen && "z-20 bg-background",
                        )}
                      >
                        {header.isPlaceholder ? null : canSort ? (
                          <button
                            type="button"
                            onClick={header.column.getToggleSortingHandler()}
                            className={cn(
                              "group inline-flex items-center gap-1",
                              meta?.align === "right" && "flex-row-reverse",
                            )}
                          >
                            {flexRender(def.header, header.getContext())}
                            <ChevronDown
                              aria-hidden
                              className={cn(
                                "size-4 shrink-0 transition",
                                sorted
                                  ? "text-foreground"
                                  : "invisible text-muted-foreground group-hover:visible group-focus-visible:visible",
                                sorted === "asc" && "rotate-180",
                              )}
                            />
                          </button>
                        ) : (
                          flexRender(def.header, header.getContext())
                        )}
                      </TableHead>
                    )
                  })}
                </TableRow>
              ))}
            </TableHeader>

            <TableBody
              className={cn(isPending && "opacity-60 transition-opacity")}
            >
              {errorMessage != null ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell
                    colSpan={colSpan}
                    role="alert"
                    className="py-6 text-center text-destructive"
                  >
                    {errorMessage}
                  </TableCell>
                </TableRow>
              ) : isLoading ? (
                Array.from({ length: SKELETON_ROWS }, (_, i) => (
                  <TableRow key={i} className="hover:bg-transparent">
                    <TableCell colSpan={colSpan}>
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : rows.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell
                    colSpan={colSpan}
                    className="py-6 text-center text-muted-foreground"
                  >
                    {noDataMessage}
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((row) => (
                  <React.Fragment key={row.id}>
                    <TableRow
                      className={cn(
                        "group/row",
                        onRowClick && "cursor-pointer",
                        getRowClassName?.(row),
                      )}
                      onClick={
                        onRowClick
                          ? (event) => onRowClick(row, event)
                          : undefined
                      }
                    >
                      {row.getVisibleCells().map((cell, index) => {
                        const meta = cell.column.columnDef.meta
                        const freeze = freezeInfo[index] ?? NOT_FROZEN
                        return (
                          <TableCell
                            key={cell.id}
                            style={{
                              ...widthStyle(meta),
                              ...freezeStyle(freeze),
                            }}
                            className={cn(
                              density === "compact" && "px-2 py-1 text-xs",
                              meta?.align === "right" &&
                                "text-right tabular-nums",
                              hasFrozen && "border-b",
                              freeze.frozen &&
                                "z-10 bg-background group-hover/row:bg-muted",
                            )}
                          >
                            {flexRender(
                              cell.column.columnDef.cell,
                              cell.getContext(),
                            )}
                          </TableCell>
                        )
                      })}
                    </TableRow>
                    {renderSubComponent && row.getIsExpanded() && (
                      <TableRow className="hover:bg-transparent">
                        <TableCell
                          colSpan={colSpan}
                          className="whitespace-normal"
                        >
                          {renderSubComponent(row)}
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))
              )}
            </TableBody>

            {showFooter && (
              <TableFooter
                className={cn(maxScrollHeight && "sticky bottom-0 z-10")}
              >
                {table.getFooterGroups().map((footerGroup) => (
                  <TableRow key={footerGroup.id}>
                    {footerGroup.headers.map((header, index) => {
                      const meta = header.column.columnDef.meta
                      const freeze = freezeInfo[index] ?? NOT_FROZEN
                      return (
                        <TableCell
                          key={header.id}
                          style={{
                            ...widthStyle(meta),
                            ...freezeStyle(freeze),
                          }}
                          className={cn(
                            meta?.align === "right" &&
                              "text-right tabular-nums",
                            freeze.frozen && "z-10 bg-muted",
                          )}
                        >
                          {header.isPlaceholder
                            ? null
                            : flexRender(
                                header.column.columnDef.footer,
                                header.getContext(),
                              )}
                        </TableCell>
                      )
                    })}
                  </TableRow>
                ))}
              </TableFooter>
            )}
          </table>
        </div>
      )}

      <DataTablePager
        table={table}
        totalCount={
          isServer
            ? mode.controls.totalCount
            : table.getFilteredRowModel().rows.length
        }
        disabled={isPending || isLoading}
      />
    </div>
  )
}

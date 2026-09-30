"use client"

import { DataTableCore, type DataTableBaseProps } from "./data-table-core"
import type { ServerTableControls } from "./table-state"

export type ServerDataTableProps<TData, TValue> = DataTableBaseProps<
  TData,
  TValue
> & {
  controls: ServerTableControls
  /** the query's `isPlaceholderData`: the previous page is on screen while the next loads */
  isPending?: boolean
}

/**
 * One page of rows from the server. Sort and page changes go back through
 * `controls`; the caller's generated hook fetches. Props-only by design: it
 * must never render anything of its own. Search input and filter panel go in
 * `toolbar`, chips in `belowToolbar`.
 */
export function ServerDataTable<TData, TValue>({
  controls,
  isPending,
  ...props
}: ServerDataTableProps<TData, TValue>) {
  return (
    <DataTableCore
      {...props}
      isPending={isPending}
      mode={{ kind: "server", controls }}
    />
  )
}

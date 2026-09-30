"use client"

import * as React from "react"
import { labels } from "../labels"
import { DataTableCore, type DataTableBaseProps } from "./data-table-core"

export type ClientDataTableProps<TData, TValue> = DataTableBaseProps<
  TData,
  TValue
> & {
  /** fuzzy search across all columns, in memory */
  searchable?: boolean
  searchPlaceholder?: string
  pageSize?: number
}

/** Every row is passed in; sorting, search and paging happen in memory. */
export function ClientDataTable<TData, TValue>({
  searchable = false,
  searchPlaceholder = labels.search,
  pageSize = 10,
  ...props
}: ClientDataTableProps<TData, TValue>) {
  const [search, setSearch] = React.useState("")
  return (
    <DataTableCore
      {...props}
      mode={{
        kind: "client",
        pageSize,
        search: searchable
          ? {
              value: search,
              onChange: setSearch,
              placeholder: searchPlaceholder,
            }
          : undefined,
      }}
    />
  )
}

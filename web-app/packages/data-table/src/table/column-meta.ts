import type { RowData } from "@tanstack/react-table"

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    /** Fixed CSS width, e.g. "8rem". Sets width, min and max. */
    width?: string
    /** "right" right-aligns header and cells (numbers, money) with tabular figures. */
    align?: "left" | "right"
  }
}

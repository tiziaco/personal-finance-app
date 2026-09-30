// Column types for feature code, so a portal needs no @tanstack/react-table
// dependency of its own. Importing this also applies the `meta` augmentation.
import "./column-meta"

export type {
  CellContext,
  ColumnDef,
  Row,
  SortingState,
  VisibilityState,
} from "@tanstack/react-table"

# Data Tables

Every table in the app is one of two components from `@app/data-table`
(`packages/data-table/src/table/`); the package source is the reference for their props. Where a
table's rows come from is `data-access.md`; a list whose state lives in the URL is `url-state.md`.
Paths below are relative to `web-app/`.

- **`ClientDataTable`** — you pass every row. Sorting, search and paging happen in memory.
- **`ServerDataTable`** — you pass one page. It reports sort and page changes; your generated hook
  fetches.

Both render the internal `DataTableCore`, which the package does not export. A new table feature is
an optional prop on the core, never a third component or a wrapper that adds JSX around these two.

## Which table

1. Can every row be sent to the browser at once — a small, bounded list? **`ClientDataTable`**.
2. Otherwise **`ServerDataTable`**, and its state lives in:
   - **the URL**, when the list is the page's main content — `url-state.md`;
   - **`useLocalTableState`**, inside a dialog, drawer, popover or secondary panel. Paging in the URL
     would make Back page the table instead of closing the dialog.

## Rows come from a generated hook

A table is a client component calling the generated hook for its route
(`@app/api-client/endpoints/<tag>`); the page around it stays a Server Component (`pages.md`).

```tsx
const state = useLocalTableState<ItemFilters>({ initialFilters: { status: null } })
const { data, isPending, isPlaceholderData, isError } = useListItems(
  toListQuery(state.query, ITEMS_PAGE_SIZE) as ListItemsParams,
  { query: { placeholderData: keepPreviousData } },
)

<ServerDataTable
  columns={columns}
  data={data?.items ?? []}
  controls={toServerTableControls(state, { pageSize: ITEMS_PAGE_SIZE, totalCount: data?.total ?? 0 })}
  isLoading={isPending}
  isPending={isPlaceholderData}
  errorMessage={isError && !data ? messages.toasts.genericError : undefined}
  toolbar={<TableSearchInput value={state.search} onChange={state.setSearch} placeholder="Search items" />}
/>
```

- **The API contract** is `offset`/`limit` → `items`/`total`, plus `ordering` and `search`
  (`server-patterns`, `references/api-routes.md`). `toListQuery` turns the 1-based page into
  `offset`/`limit` and spreads `filters` as-is; if filter names differ from the API's, map
  `state.query.filters` yourself and wrap the result in `compactQuery`.
- **Only `state.query` goes into the request.** `state.search` is what the input shows;
  `state.query.search` is debounced (300 ms).
- **`isLoading={isPending}`** — skeleton rows on the first load, never "No results.".
  **`isPending={isPlaceholderData}`** — dims the previous page while the next loads. Not
  `isFetching`: that is also true on a background refetch, and dims a table nothing changed.
- **Errors.** `QueryProvider` has already toasted from `error.status`. `errorMessage` only replaces
  the empty state, with curated copy from `@app/core/constants/messages` — never `error.message`.
- **The `as ListItemsParams` cast** narrows `ordering` from `string` to the route's allow-list. It
  holds because every sortable column id is an allow-listed field (Columns, below).
- **In a dialog**, call `useLocalTableState` and the hook in a component rendered inside
  `DialogContent`. The popup unmounts when closed, so search, page and filters reset on each open and
  nothing fetches while closed.
- **A picker dialog feeding a URL-driven list** reports the pick through a stable callback; the list's
  owner applies it with its own `setFilters`. The dialog never touches the URL.

## Build a table

- [ ] Columns in a `use<Domain>Columns()` hook, `use-<domain>-columns.tsx`, next to the table.
- [ ] Page size a named constant (`ITEMS_PAGE_SIZE`), at most the route's `limit` cap (100).
- [ ] Client: `<ClientDataTable columns data isLoading searchable? pageSize? />`. A bounded list that
      should show every row: set `pageSize` to the row count; the default is 10.
- [ ] Server: `controls` from `toServerTableControls`, `isLoading` and `isPending` from the query.
      Search input and filter panel in `toolbar`, chips in `belowToolbar`.
- [ ] `noDataMessage` says what is empty ("No items match.").
- [ ] Row actions call `event.stopPropagation()` if the row also has `onRowClick`, and a row with
      `onRowClick` also exposes the action as a button or link in a cell — keyboard users can't click
      a row.

## Columns

```tsx
import type { ColumnDef } from "@app/data-table/columns"

export function useOrderColumns({ canEdit, onEdit }: { canEdit: boolean; onEdit: (o: OrderResponse) => void }) {
  return useMemo<ColumnDef<OrderResponse>[]>(() => [
    { accessorKey: "number", id: "number", header: "Order" },
    { accessorKey: "customer_name", id: "customer_name", header: "Customer", enableSorting: false },
    { accessorKey: "total", id: "total", header: "Total", meta: { align: "right" } },
    {
      id: "actions",
      header: "",
      enableSorting: false,
      cell: ({ row }) => (canEdit ? <Button size="sm" onClick={() => onEdit(row.original)}>Edit</Button> : null),
    },
  ], [canEdit, onEdit])
}
```

- Types come from `@app/data-table/columns` — the app has no `@tanstack/react-table` dependency —
  and row types from `@app/api-client/types`.
- The hook's parameters equal its `useMemo` deps. Pass narrowed values (`canEdit`, not `user`), and
  callbacks the caller wrapped in `useCallback` — a new function each render rebuilds every column.
- **Server tables: every column makes a sorting decision.** Its `id` is a field in the route's
  `ordering` allow-list, or it sets `enableSorting: false`. TanStack sorts by default, so a column
  without a decision sends an `ordering` the route answers with a 422.
- Format values in `cell`, with `Intl` formatters hoisted to module scope.
- `meta.width` ("8rem") and `meta.align` ("right" for numbers and money), never inline styles.
- A header that isn't a string (icons, checkboxes) needs an `id`, and `enableSorting: false` unless
  it sorts.

## Props

| Prop | Use |
| --- | --- |
| `title`, `headerActions` | heading and right-aligned actions above the table |
| `toolbar`, `belowToolbar` | search + filter panel; filter chips |
| `searchable`, `searchPlaceholder`, `pageSize` | `ClientDataTable` only |
| `controls`, `isPending` | `ServerDataTable` only |
| `isLoading` | skeleton rows on the first load |
| `noDataMessage`, `errorMessage` | empty body; curated error copy shown instead of rows |
| `onRowClick`, `getRowClassName`, `getRowId` | row behaviour; `getRowId` defaults to `row.id` |
| `renderSubComponent` | expander column + content under the row |
| `getSubRows` | nested rows expandable in place |
| `showFooter` | renders `footer` column defs (totals) |
| `freezeColumns={{ left, right }}` | sticky columns during horizontal scroll |
| `maxScrollHeight` | scrolling body with a sticky header |
| `density="compact"` | tighter rows for dense data |
| `showColumnToggle`, `defaultColumnVisibility`, `columnVisibility` + `onColumnVisibilityChange` | column visibility |

**Remembered column visibility:** spread `useStoredColumnVisibility(key, DEFAULTS)` from
`@app/data-table/use-stored-column-visibility` into the table. It is SSR-safe
(`useSyncExternalStore`), and `DEFAULTS` must be a module constant. For per-user server storage, keep
the same controlled shape and save, debounced, in the setter; the table never resets a controlled
value from props.

## Selection, bulk actions and phone cards

- **Selection:** `enableRowSelection` adds a checkbox column. `renderBulkActions(selected, clearSelection)`
  fills the bulk bar ("N selected", Clear, your actions). Selection holds only rows on screen and is
  committed to state, so a row that leaves the page and returns stays deselected, and a bulk action
  never touches a row the user cannot see. The bar is a pill fixed to the bottom of the viewport,
  centred on the table by measuring it (so it never covers the sidebar), with an in-flow spacer
  after the pager so the page can scroll clear of it. Not sticky: the dashboard scrolls the window,
  and its `overflow-auto` content wrapper would capture a sticky bar without ever scrolling. It is
  desktop only: hidden in card mode.
- **One toolbar height:** every control in a table's toolbar and page header is the default 32px —
  `Button` with no `size` (`icon` for an icon-only one), `Input`, `SelectTrigger size="sm"` (its
  default is 36px). `sm` buttons are for compact spots: the bulk-action pill, the date presets.
- **The frame:** every table sits in a card (`rounded-xl border bg-card shadow-sm`) with uppercase
  muted header labels on a `bg-muted/50` strip. Sticky and frozen header cells use opaque `bg-muted`.
- **Phone cards:** `renderCard(row)` replaces the body with a card list below 768px (`useIsMobile`).
  Toolbar, chips and pager stay; column headers, row menus and the bulk bar do not. So a card that
  acts is a `<button>` (the transactions card opens the edit dialog), and a list that sorts needs a
  control of its own — transactions puts one in `headerActions` on every screen size — writing
  through the state hook's `setSort(orderingToSorting(value))` so the page resets as a header click
  would.
- **Date presets:** `DateFilterControl` takes `presets` — today, this week (Monday first), this month,
  last month — from `@app/data-table/url-state/date-presets`.
- **Several values from a fixed list:** `FilterCheckboxGroup`, from
  `@app/data-table/filters/filter-checkbox-group`.
- **The filter panel** is a right-hand sheet (full width on a phone): a header with "N active", one
  ruled section per child, "Clear all filters" at the bottom while any is active. A field with one
  input is a `FilterField`; several inputs under one title (a min and a max) go in a `FilterSection`.
- **Selects and dates are Base UI, never native:** a pick-one field is `@app/ui/select`, and a
  filter's "any" is a `null` item (`items` with `{ value: null, label: "Any …" }`), which the
  trigger shows while nothing is picked. A date is `DatePicker` from
  `@app/components/forms/date-picker` — `DateFilterControl` uses both, which is why
  `@app/data-table` depends on `@app/components`.
- **Moving a page without trapping Back:** the url-state page setter takes `{ history: "replace" }`
  (the transactions page uses it to bring a past-the-end page back to the last one).
- **A mutation that handles a status itself** sets `meta.silentStatuses: number[]` so `QueryProvider`
  does not toast it (the add dialog's 409).

Worked example: `apps/web/src/components/transactions/`.

## Rules

- Feature code imports `ClientDataTable` or `ServerDataTable` — the export map doesn't offer the core.
- One state-hook call per list; don't prop-drill its result through wrapper components.
- Never `useState` a copy of `filters`, search, page or sort next to a state hook.
- The package's own strings are in `packages/data-table/src/labels.ts`; a table's own copy
  (`noDataMessage`, placeholders, headers) is written at the call site.

## Examples

`../examples/products/` — a client table over a generated hook, with remembered column visibility.
`../examples/add-items-dialog/` — a server table with local state inside a dialog, and its test
(the generated hook mocked with `vi.mock` + `vi.hoisted`). Both are written against invented routes.

## Why it is built this way

- **One body, two wrappers.** Every second implementation of a table body (a "server" variant, a
  "fetching" variant) drifted from the first: a prop added to one was missing from the other.
- **React Compiler.** `useReactTable` returns one mutable instance whose identity never changes, so a
  compiled component that receives `table` as a prop memoises against it and freezes. The core, the
  pager and the column toggle start with `"use no memo"`. The compiler is off today; a new component
  that takes `table`, a column, row or header needs the directive anyway.
- **Frozen columns** are `position: sticky`, with offsets measured by a `ResizeObserver` on the header
  cells; a single header row only.
- **Sorting** is single-column: a header click cycles ascending, descending, unsorted, and sends
  `ordering=field` or `ordering=-field`.

## Verify

- The right table for the data size, and the right state home (URL vs local).
- Every server-table column has a sorting decision; page size ≤ the route's cap.
- `isLoading` and `isPending` passed; no `error.message` rendered.
- The component's co-located test — load the `web-app-testing` skill before writing it.
- `make check-web` and `make test-web` from the repo root.

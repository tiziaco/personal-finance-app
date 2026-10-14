# URL-Driven List State

A page's main list keeps its filters, search, sort and page in the URL. **Read `data-tables.md`
first** — this file is the state half of a `ServerDataTable`. The hooks are in
`packages/data-table/src/url-state/`, built on nuqs. Paths below are relative to `web-app/`.

**The URL is the only copy of a list's state.** Every control reads it back on each render, so chips,
search box and rows can't disagree, the view is shareable, and Back works. The URL is written
`shallow`: nothing re-renders on the server. The rows come from the list's generated hook, keyed on the
state hook's `query`, so a URL change is a new query key.

`UrlStateAdapter` is already mounted next to `QueryProvider` in the signed-in route group. The app
imports nuqs only through `@app/data-table` — parsers from `@app/data-table/url-state/params`, the test
adapter from `@app/data-table/url-state/testing`.

## Files per list

In `apps/web/src/components/<area>/`:

| File | Contents |
| --- | --- |
| `<domain>-table-params.ts` | parsers, `load<Domain>TableParams` (for tests), the `<Domain>Filters` type, `to<Domain>Filters` / `from<Domain>Filters`, `to<Domain>Query`, `<DOMAIN>_PAGE_SIZE` |
| `use-<domain>-table-state.ts` | one `createUrlTableStateHook(...)` call |
| `<domain>-table.tsx` | `"use client"`: the state hook, the generated hook, the columns hook, `ServerDataTable` |
| `<domain>-filters.tsx` | the filter panel and its chips |
| `use-<domain>-columns.tsx` | columns (`data-tables.md`) |

Plus `<domain>-table-params.test.ts` and `use-<domain>-table-state.test.tsx`. The page is a Server
Component that renders `<DomainTable />` and nothing list-specific. `../examples/orders/` is the
complete reference, written against an invented `listOrders` route — copy it and rename.

## New list

- [ ] **Params file.** Parsers: `page: parseAsInteger.withDefault(1)`,
      `ordering: parseAsStringLiteral(Object.values(List<Domain>Ordering))` — the route's allow-list,
      generated as a const in `@app/api-client/types` —, `search: parseAsString.withDefault("")`, then
      one per filter. `load<Domain>TableParams = createLoader(parsers)`. The two mappers.
      `to<Domain>Query` built with `compactQuery`, paging with `toOffsetLimit(v.page, PAGE_SIZE)`,
      typed as the generated `List<Domain>Params`. Page size ≤ the route's `limit` cap.
- [ ] **Hook.** `export const use<Domain>TableState = createUrlTableStateHook({ parsers, toFilters, fromFilters })`.
      Nothing else.
- [ ] **Filter UI** on `FilterPanel` / `FilterField` / `FilterChip` / `DateFilterControl`
      (`@app/data-table/filters/*`), with `@app/ui/select` for a pick-one filter (a `null` item is
      "any"). Props `{ filters, setFilters }` plus any
      option lists. No local state, no router.
- [ ] **Table.** One state-hook call. `useList<Domain>(to<Domain>Query(state.query), { query: { placeholderData: keepPreviousData } })`.
      `controls={toServerTableControls(state, { pageSize, totalCount: data?.total ?? 0 })}`,
      `isLoading={isPending}`, `isPending={isPlaceholderData}`. `TableSearchInput` + panel in
      `toolbar`, chips in `belowToolbar`.
- [ ] **Filter options** (a customer dropdown) are their own generated query, not part of the list
      response.
- [ ] **Tests**: the params round-trip test and the hook test, copied from the example.
- [ ] **By hand**: apply a filter, sort, change the filter, press Back. Chips, search box, panel and
      rows move together.

## Add one filter

1. Confirm the route accepts the param. If the server changed, `make gen-contract` first.
2. Add the key to the parser set: `parseAsString`, `parseAsInteger`, or `parseAsStringLiteral([...] as const)`.
   A fixed option list is declared once as an `as const` array (`ORDER_STATUSES`) and reused by the
   parser, the panel and the chip labels.
3. Add it to both `to<Domain>Filters` and `from<Domain>Filters`.
4. Add the control to the panel **and** the chip to the chips, and count it in `activeCount`.
5. Forward it in `to<Domain>Query`; `compactQuery` drops it when unset.
6. Extend the round-trip test.

Skip step 3 or 4 and the filter half-works: the rows change, and nothing on screen says why.

## Add a date filter

- Three keys: `<name>_mode` (`parseAsStringLiteral(DATE_FILTER_MODES)`), `<name>_from`, `<name>_to`.
- `to…Filters`: `mode: v.<name>_mode ?? dateMode(v.<name>_from, v.<name>_to)`.
- `from…Filters`: `<name>_mode: f.<name>.mode`, `<name>_from: dateVal(f.<name>, 1)`,
  `<name>_to: dateVal(f.<name>, 2)`. Without the mode line it is never persisted; `dateVal` drops the
  date a narrower mode hides.
- `to…Query`: never forward `<name>_mode`; take the dates through `to…Filters` + `dateVal`, so a
  hand-edited link can't filter by a hidden date.
- UI: `<DateFilterControl label=… value={filters.<name>} onChange={(v) => setFilters((f) => ({ ...f, <name>: v }))} />`;
  the chip text and the active check both from `dateFilterLabel` (`isDateFilterActive` for the check
  alone).

## Two lists on one page

Prefix every URL-driven list on the page, and give each its own table component:

```ts
export const ordersUrlKeys = prefixKeys(ordersParsers, "orders")
export const loadOrdersTableParams = createLoader(ordersParsers, { urlKeys: ordersUrlKeys })

export const useOrdersTableState = createUrlTableStateHook({
  parsers: ordersParsers,
  urlKeys: ordersUrlKeys,
  toFilters: toOrdersFilters,
  fromFilters: fromOrdersFilters,
})
```

`prefixKeys` is `@app/data-table/url-state/prefix-keys`. Prefixing an existing list breaks its old
links and its tests' query strings — update both.

## Rules

- No `useState` copy of filters, search, page or sort. Ever.
- No `useSearchParams`, `router.push` or `history` in a list component. The hook owns the URL.
- History is the hook's: filter, sort and page changes push; typing a search replaces the current
  entry, debounced 300 ms (`SEARCH_DEBOUNCE_MS`). Back after a search goes to the entry before the one
  it replaced. Don't repeat any of it in components.
- The request is built from `state.query`, never from `state.search` or the raw URL: `query` holds a
  typed search back until the user pauses, so a keystroke is not a request.
- One parser set per API contract: a key `to<Domain>Query` doesn't forward doesn't belong in it.
- One state-hook call per list; don't wrap it in a component that only forwards its result.
- Tables in dialogs or drawers use `useLocalTableState` (`data-tables.md`), never URL state.

## Testing

- **Params**: `load…(new URLSearchParams("…"))`, then `from(to(values))` keeps every key; narrowing a
  date mode drops the hidden date; `to…Query` has offset/limit, no `*_mode` and no unset keys; an
  ordering outside the allow-list parses to `null`.
- **Hook**: `renderHook(…, { wrapper: withNuqsTestingAdapter({ searchParams, onUrlUpdate }) })`. nuqs
  flushes writes asynchronously, so await the setter inside `act`:
  `await act(async () => { await result.current.setFilters(…) })`.
- A test that reads the state back after a write passes `hasMemory: true`; without it the adapter
  returns to `searchParams` on the next render.
- The component test mocks the generated hook (`web-app-testing`) and asserts the params it was
  called with.

## Why it is built this way

- **The URL is the only copy** because the bug it removes is controls that read the URL once on mount
  and kept their own state: after Back the rows were right and the chips were not.
- **Shallow, with a client query**, because in this repo the generated hooks are client-only
  (`data-access.md`). A server-rendered list would give up the token, `ApiError` and the error toasts.
- **The mode of a date filter is its own key**: "mode picked, no date yet" and "no filter" look the
  same from the dates alone. The server filters on the dates, so the mode is never sent.
- **One parser set per contract**: two lists sharing one render a chip for a filter one API never
  receives.
- **Prefixes**: without one, a list owns the bare `page`, `ordering` and `search` keys, and two lists
  fight over them.

## Verify

- The files are laid out as above; nothing list-specific inline in `page.tsx`.
- Every filter key (not `page`, `ordering`, `search`) is mapped both ways, shown as a chip, counted as
  active, and forwarded — except `*_mode`.
- Prefixes when the page has more than one URL list.
- Both tests present; `make check-web` and `make test-web` from the repo root.

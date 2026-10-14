# Transactions: the legacy look — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring back legacy's table frame, right-hand filter sheet, floating bulk bar and one-row toolbar on `/transactions`, keeping step 2's filters, chips and header sorting.

**Architecture:** The table frame, the sheet and the bar live in the shared `@app/data-table` package (its only consumer today is `/transactions`, so every later list inherits them). The sort control, the page header and the filter contents are page code in `apps/web/src/components/transactions/`. No server, contract or theme change.

**Tech Stack:** Next.js 16, React 19, Tailwind v4, Base UI (`render` prop, never `asChild`), TanStack Table, nuqs, Vitest + Testing Library.

**Spec:** `.superpowers/specs/2026-10-14-transactions-legacy-look-design.md` (decisions D1–D6).

## Global Constraints

- Base UI, not Radix: `render={<Button … />}`, never `asChild`.
- Every string `@app/data-table` renders comes from `packages/data-table/src/labels.ts`.
- No theme changes: no edits to colour tokens, fonts or `globals.css`. Use existing tokens (`bg-card`, `bg-muted`, `text-muted-foreground`, `border`, `shadow-sm`, `shadow-lg`).
- Phone cards (`renderCard`, below 768px) keep their current look and behaviour; the bulk bar stays hidden in card mode.
- Every web gate runs all four, from `web-app/` unless noted: `pnpm type-check`, `pnpm test`, and from the repo root `make check-web`. `make check-web` skips tsc, so `pnpm type-check` is not optional.
- Never commit or push with `--no-verify`. Never hand-edit `packages/api-client/src/generated/`.
- Tests are co-located (`x.test.tsx` next to `x.tsx`). Before writing a test, read the `/web-app-testing` skill; before touching `packages/` or `apps/web/src/`, read `/web-app-patterns`.

## Review Focus

1. **A long table while rows are selected:** the floating bar stays in view at the bottom of the dashboard's scroll container (`(dashboard)/layout.tsx`, `div.flex-1.overflow-auto`), centred on the table, never behind the sidebar. *(Visual — checked in the browser pass after Task 3.)*
2. **The filter sheet on a 390px phone:** full width, its body scrolls, the × stays reachable, the footer never covers the last section. *(Visual — browser pass.)*
3. **`?recurring=false` from an old link:** the chip reads "Not recurring", the badge counts 1, the switch shows off, and turning it on asks for recurring only. *(Test in Task 3.)*
4. **Header click and sort control disagree:** after a header sets `ordering=amount`, the select must show Amount and the arrow ascending; with no `ordering` it shows Date, descending. *(Test in Task 3.)*
5. **Sticky or frozen headers** (`maxScrollHeight`, `freezeColumns`): header cells stay opaque (`bg-muted`), so scrolled rows never show through. *(Task 1 code; visual.)*

---

### Task 1: The table frame and the floating bulk bar (`@app/data-table`)

**Files:**
- Modify: `web-app/packages/data-table/src/table/data-table-core.tsx`
- Modify: `web-app/packages/data-table/src/table/data-table-bulk-bar.tsx`
- Modify: `web-app/packages/data-table/src/table/data-table-pager.tsx` (the outer `className`)
- Modify: `web-app/packages/data-table/src/table/table-search-input.tsx`
- Modify: `web-app/packages/data-table/src/labels.ts`
- Test: `web-app/packages/data-table/src/table/data-table-selection.test.tsx`
- Docs: `.claude/skills/web-app-patterns/references/data-tables.md`

**Interfaces:**
- Consumes: nothing new.
- Produces: `labels.selected = "selected"`. `DataTableBulkBar` keeps its props (`count`, `onClear`, `children`), its `role="toolbar"` / `aria-label={labels.bulkActions}`, and still renders the text `labels.selectedCount(count)` ("2 selected"), now `sr-only`. Task 3's tests find "2 selected" by text.

- [ ] **Step 1: Write the failing test** — append to the top-level `describe` in `data-table-selection.test.tsx` (it already has `renderTable(page1)` and checks "1 selected"):

```tsx
  it("floats the bulk bar after the table, not above it", async () => {
    renderTable(page1)
    await userEvent.click(screen.getAllByRole("checkbox", { name: "Select row" })[0])
    const bar = screen.getByRole("toolbar", { name: "Bulk actions" })
    const table = screen.getByRole("table")
    // after the table in document order: it overlays the rows, it does not push them down
    expect(
      table.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    // the count reads as one phrase for screen readers
    expect(within(bar).getByText("1 selected")).toBeInTheDocument()
  })
```

Add `within` to the file's `@testing-library/react` import if it is missing.

- [ ] **Step 2: Run it to verify it fails**

Run (from `web-app/`): `pnpm vitest run packages/data-table/src/table/data-table-selection.test.tsx`
Expected: the new test FAILS on the document-position assertion (the bar renders before the table today).

- [ ] **Step 3: Add the label** — in `labels.ts`, after `selectedCount`:

```ts
  selected: "selected",
```

- [ ] **Step 4: Rewrite the bulk bar** — replace the whole of `data-table-bulk-bar.tsx`:

```tsx
"use client"

import type { ReactNode } from "react"
import { X } from "lucide-react"
import { Button } from "@app/ui/button"
import { labels } from "../labels"

/**
 * A pill floating under the table: the count, the page's actions, Clear.
 * Sticky to the bottom of the scroll container, so on a long page it stays in
 * view over the rows. Rendered by DataTableCore while rows are selected.
 */
export function DataTableBulkBar({
  count,
  onClear,
  children,
}: {
  count: number
  onClear: () => void
  children?: ReactNode
}) {
  return (
    <div className="pointer-events-none sticky bottom-6 z-30 mt-3 flex justify-center">
      <div
        role="toolbar"
        aria-label={labels.bulkActions}
        className="pointer-events-auto flex animate-in items-center gap-3 rounded-xl border bg-card px-4 py-2 shadow-lg duration-200 fade-in slide-in-from-bottom-4"
      >
        <span className="sr-only">{labels.selectedCount(count)}</span>
        <span aria-hidden className="flex items-center gap-2">
          <span className="flex h-6 min-w-6 items-center justify-center rounded-lg bg-primary px-1.5 text-sm font-semibold text-primary-foreground tabular-nums">
            {count}
          </span>
          <span className="text-sm font-medium text-muted-foreground">
            {labels.selected}
          </span>
        </span>
        <div className="flex items-center gap-2">{children}</div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onClear}
          aria-label={labels.clearSelection}
        >
          <X />
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Move the bar below the table** — in `data-table-core.tsx`, cut this block from above `{asCards ? (`:

```tsx
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
```

and paste it, unchanged, between the end of the `{asCards ? (…) : (…)}` expression and `<DataTablePager`.

- [ ] **Step 6: Frame the table** — in `data-table-core.tsx`, four edits:

(a) the table container's classes:

```tsx
          className={cn(
            "relative w-full overflow-x-auto rounded-xl border bg-card shadow-sm",
            hasFrozen && "overflow-y-clip",
            maxScrollHeight && "overflow-y-auto",
          )}
```

(b) the `<table>`: `"w-full caption-bottom text-xs"` → `"w-full caption-bottom text-sm"`.

(c) the header row and header cells:

```tsx
                <TableRow key={headerGroup.id} className="bg-muted/50 hover:bg-muted/50">
```

```tsx
                        className={cn(
                          "text-xs font-medium tracking-wider text-muted-foreground uppercase",
                          density === "compact" ? "h-8 px-2" : "h-9 px-4",
                          wraps && "whitespace-normal",
                          meta?.align === "right" && "text-right",
                          hasFrozen && "border-b",
                          maxScrollHeight && "sticky top-0 z-10 bg-muted",
                          freeze.frozen && "z-20 bg-muted",
                        )}
```

(d) the body cells:

```tsx
                            className={cn(
                              density === "compact"
                                ? "px-2 py-1 text-xs"
                                : "px-4 py-2.5",
                              meta?.align === "right" &&
                                "text-right tabular-nums",
                              hasFrozen && "border-b",
                              freeze.frozen &&
                                "z-10 bg-card group-hover/row:bg-muted",
                            )}
```

Leave the footer cells as they are.

- [ ] **Step 7: Pager and search width** — in `data-table-pager.tsx`, the outer `className="flex items-center justify-between border-t py-3"` → `className="flex items-center justify-between py-3"` (the table now has its own frame; a rule under it doubles the line). In `table-search-input.tsx`, `"relative w-full max-w-xs"` → `"relative w-full sm:w-64"` (a `w-full` flex item pushed Filters onto a second line; from 640px it is a fixed 16rem).

- [ ] **Step 8: Run the package tests**

Run: `pnpm vitest run packages/data-table`
Expected: all PASS, including the new test. If an existing test asserted `border-t` on the pager or `max-w-xs` on the search input, update it to the new class.

- [ ] **Step 9: Docs** — in `data-tables.md`, "Selection, bulk actions and phone cards", replace the **Selection** bullet's last sentence ("The bar is desktop only: it is hidden in card mode.") with:

```md
  The bar is a pill floating under the table, sticky to the bottom of the scroll container so it stays
  in view over a long page. It is desktop only: hidden in card mode.
```

and add a bullet before **Phone cards**:

```md
- **The frame:** every table sits in a card (`rounded-xl border bg-card shadow-sm`) with uppercase
  muted header labels on a `bg-muted/50` strip. Sticky and frozen header cells use opaque `bg-muted`.
```

- [ ] **Step 10: Gate and commit**

Run (from `web-app/`): `pnpm type-check && pnpm test`, then from the repo root `make check-web`.
Expected: all exit 0.

```bash
git add web-app/packages/data-table .claude/skills/web-app-patterns/references/data-tables.md
git commit -m "feat(data-table): tables sit in a card; the bulk bar floats under the table"
```

---

### Task 2: The filter panel becomes a right-hand sheet (`@app/data-table`)

**Files:**
- Modify: `web-app/packages/data-table/src/filters/filter-panel.tsx`
- Modify: `web-app/packages/data-table/src/filters/filter-checkbox-group.tsx`
- Modify: `web-app/packages/data-table/src/labels.ts`
- Test: `web-app/packages/data-table/src/filters/filter-panel.test.tsx`
- Docs: `.claude/skills/web-app-patterns/references/data-tables.md`

**Interfaces:**
- Consumes: `Sheet`, `SheetTrigger`, `SheetContent`, `SheetHeader`, `SheetTitle`, `SheetDescription`, `SheetFooter` from `@app/ui/sheet` (exists).
- Produces: `FilterPanel` keeps its props (`activeCount`, `onClearAll`, `label?`, `children`, `className?`); each top-level child of `FilterPanel` is one ruled section. New export `FilterSection({ title, children })` from `@app/data-table/filters/filter-panel` — a `<fieldset>` with an uppercase `<legend>`, for a section holding several inputs (Task 3 uses it for the amount range). New export `FILTER_SECTION_TITLE` (the title classes). `labels.clearAll` now reads "Clear all filters"; new `labels.activeCount(n)` → `"2 active"`.

- [ ] **Step 1: Write the failing tests** — replace the whole of `filter-panel.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { FilterPanel, FilterSection } from "./filter-panel"

describe("FilterPanel", () => {
  it("opens a sheet with the active count, and clears all from its footer", async () => {
    const onClearAll = vi.fn()
    render(
      <FilterPanel activeCount={2} onClearAll={onClearAll}>
        <p>fields</p>
      </FilterPanel>,
    )
    const trigger = screen.getByRole("button", { name: /Filters/ })
    expect(trigger).toHaveTextContent("2")
    await userEvent.click(trigger)
    const sheet = await screen.findByRole("dialog", { name: "Filters" })
    expect(within(sheet).getByText("2 active")).toBeInTheDocument()
    expect(within(sheet).getByText("fields")).toBeInTheDocument()
    await userEvent.click(
      within(sheet).getByRole("button", { name: "Clear all filters" }),
    )
    expect(onClearAll).toHaveBeenCalled()
  })

  it("has no count and no Clear all when nothing is active", async () => {
    render(
      <FilterPanel activeCount={0} onClearAll={() => {}}>
        <p>fields</p>
      </FilterPanel>,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const sheet = await screen.findByRole("dialog", { name: "Filters" })
    expect(within(sheet).queryByText(/active/)).toBeNull()
    expect(
      within(sheet).queryByRole("button", { name: "Clear all filters" }),
    ).toBeNull()
  })

  it("closes from its close button", async () => {
    render(
      <FilterPanel activeCount={0} onClearAll={() => {}}>
        <p>fields</p>
      </FilterPanel>,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const sheet = await screen.findByRole("dialog", { name: "Filters" })
    await userEvent.click(within(sheet).getByRole("button", { name: "Close" }))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })
})

describe("FilterSection", () => {
  it("names its group by the title", () => {
    render(
      <FilterSection title="Amount range">
        <input aria-label="Min" />
      </FilterSection>,
    )
    expect(
      screen.getByRole("group", { name: "Amount range" }),
    ).toContainElement(screen.getByLabelText("Min"))
  })
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pnpm vitest run packages/data-table/src/filters/filter-panel.test.tsx`
Expected: FAIL — no `dialog` role (it is a popover today) and `FilterSection` is not exported.

- [ ] **Step 3: Labels** — in `labels.ts`: `clearAll: "Clear all",` → `clearAll: "Clear all filters",`, and after `activeFilters` add:

```ts
  activeCount: (n: number) => `${n} active`,
```

- [ ] **Step 4: Rewrite `FilterPanel` and `FilterField`, add `FilterSection`** — in `filter-panel.tsx`, replace the imports, `FilterPanel` and `FilterField` (keep `FilterSelect` exactly as it is):

```tsx
"use client"

import type { ComponentProps, ReactNode } from "react"
import { ListFilter } from "lucide-react"
import { Button } from "@app/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@app/ui/sheet"
import { cn } from "@app/core/lib/utils"
import { labels } from "../labels"

/** The title style every filter section shares. */
export const FILTER_SECTION_TITLE =
  "text-xs font-semibold tracking-wider text-muted-foreground uppercase"

/**
 * A right-hand sheet for a list's filters; full width on a phone. Each child
 * is one ruled section. The fields inside are per list and read/write only
 * through `filters` / `setFilters`: no local state.
 */
export function FilterPanel({
  activeCount,
  onClearAll,
  label = labels.filters,
  children,
  className,
}: {
  activeCount: number
  onClearAll: () => void
  label?: string
  children: ReactNode
  className?: string
}) {
  return (
    <Sheet>
      <SheetTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            className={cn(activeCount > 0 && "border-primary text-primary")}
          />
        }
      >
        <ListFilter />
        {label}
        {activeCount > 0 && (
          <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground tabular-nums">
            {activeCount}
            <span className="sr-only"> {labels.activeFilters}</span>
          </span>
        )}
      </SheetTrigger>
      <SheetContent
        side="right"
        className={cn("gap-0 data-[side=right]:w-full", className)}
      >
        <SheetHeader className="border-b pr-12">
          <SheetTitle>{label}</SheetTitle>
          {activeCount > 0 && (
            <SheetDescription className="text-xs">
              {labels.activeCount(activeCount)}
            </SheetDescription>
          )}
        </SheetHeader>
        <div className="flex-1 divide-y overflow-y-auto px-4 *:py-5">
          {children}
        </div>
        {activeCount > 0 && (
          <SheetFooter className="border-t">
            <Button variant="outline" className="w-full" onClick={onClearAll}>
              {labels.clearAll}
            </Button>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  )
}

/** One labelled input: a section of its own, or a field inside a FilterSection. */
export function FilterField({
  label,
  htmlFor,
  children,
}: {
  label: string
  htmlFor: string
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <label htmlFor={htmlFor} className={cn("block", FILTER_SECTION_TITLE)}>
        {label}
      </label>
      {children}
    </div>
  )
}

/** A section holding several inputs under one title (e.g. a min and a max). */
export function FilterSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <fieldset className="space-y-2">
      <legend className={cn("mb-2", FILTER_SECTION_TITLE)}>{title}</legend>
      {children}
    </fieldset>
  )
}
```

`data-[side=right]:w-full` is deliberate: `SheetContent`'s own `data-[side=right]:w-3/4` outranks a plain `w-full` (class + attribute selector), so only the same variant overrides it. Its `data-[side=right]:sm:max-w-sm` still caps it at 24rem from 640px.

- [ ] **Step 5: The checkbox group shows every option** — in `filter-checkbox-group.tsx`, import `FILTER_SECTION_TITLE` from `"./filter-panel"` and `cn` from `"@app/core/lib/utils"`, then:

```tsx
    <fieldset className="space-y-2">
      <legend className={cn("mb-2", FILTER_SECTION_TITLE)}>{label}</legend>
      <div className="space-y-1.5">
```

(the inner `max-h-48 overflow-y-auto pr-1` goes: the sheet scrolls, so all options show).

- [ ] **Step 6: Run the package tests**

Run: `pnpm vitest run packages/data-table`
Expected: all PASS. `date-filter-control.test.tsx` and `filter-checkbox-group.test.tsx` find fields by label and role, so the restyle leaves them green; if one asserted the old "Clear all" text, update it to "Clear all filters".

- [ ] **Step 7: Docs** — in `data-tables.md`, add after the **Several values from a fixed list** bullet:

```md
- **The filter panel** is a right-hand sheet (full width on a phone): a header with "N active", one
  ruled section per child, "Clear all filters" at the bottom while any is active. A field with one
  input is a `FilterField`; several inputs under one title (a min and a max) go in a `FilterSection`.
```

- [ ] **Step 8: Gate and commit**

Run (from `web-app/`): `pnpm type-check && pnpm test` — the web project's `transaction-filters.test.tsx` must stay green (Task 3 changes it next) — then from the repo root `make check-web`.

```bash
git add web-app/packages/data-table .claude/skills/web-app-patterns/references/data-tables.md
git commit -m "feat(data-table): the filter panel is a right-hand sheet with ruled sections"
```

---

### Task 3: The transactions page — header row, sort control, filter contents

**Files:**
- Modify: `web-app/apps/web/src/app/(dashboard)/transactions/page.tsx`
- Modify: `web-app/apps/web/src/components/transactions/transactions-table.tsx`
- Modify: `web-app/apps/web/src/components/transactions/transactions-sort-select.tsx`
- Modify: `web-app/apps/web/src/components/transactions/transaction-filters.tsx`
- Test: `web-app/apps/web/src/components/transactions/transactions-table.test.tsx`
- Test: `web-app/apps/web/src/components/transactions/transaction-filters.test.tsx`
- Docs: `docs/product/features/transactions.md`, `.claude/skills/web-app-patterns/references/data-tables.md`

**Interfaces:**
- Consumes: `FilterPanel`, `FilterSection`, `FilterSelect` (Task 2); `labels.selectedCount` text "N selected" (Task 1); `ListTransactionsOrdering` from `@app/api-client/types` (`"date" | "-date" | "amount" | "-amount" | "merchant" | "-merchant"`); `state.setSort(orderingToSorting(ordering))` from `use-transactions-table-state` / `@app/data-table/table-state` (exists).
- Produces: `TransactionsSortControl({ ordering, onChange })` exported from `transactions-sort-select.tsx`, replacing `TransactionsSortSelect`. The page's `<h1>` moves from `page.tsx` into `TransactionsTable`.

- [ ] **Step 1: Write the failing tests** — in `transactions-table.test.tsx`:

(a) inside `describe("on a phone", …)`, replace the test `"sorts from a select: writes ordering and resets the page"` with:

```tsx
    it("keeps the sort control on a phone", async () => {
      result([row])
      renderAt()
      expect(
        await screen.findByRole("combobox", { name: "Sort by" }),
      ).toBeInTheDocument()
    })
```

(b) replace the test `"has no sort select on a wide screen: the headers sort"` with:

```tsx
  it("sorts by field from the toolbar, keeping the direction and resetting the page", async () => {
    result([row], 60)
    const events: UrlUpdateEvent[] = []
    renderAt("?page=3", (e) => events.push(e))
    const field = await screen.findByRole("combobox", { name: "Sort by" })
    expect(field).toHaveValue("date")
    expect(
      within(field)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["Date", "Amount", "Merchant"])
    expect(
      screen.getByRole("button", { name: "Sort descending" }),
    ).toBeInTheDocument()

    await userEvent.selectOptions(field, "amount")
    await waitFor(() =>
      expect(events.at(-1)?.searchParams.get("ordering")).toBe("-amount"),
    )
    expect(events.at(-1)?.searchParams.get("page")).toBeNull()
  })

  it("flips the direction from the arrow button", async () => {
    result([row])
    const events: UrlUpdateEvent[] = []
    renderAt("?ordering=-amount", (e) => events.push(e))
    await userEvent.click(
      await screen.findByRole("button", { name: "Sort descending" }),
    )
    await waitFor(() =>
      expect(events.at(-1)?.searchParams.get("ordering")).toBe("amount"),
    )
  })

  it("shows what a header click chose", async () => {
    result([row])
    renderAt("?ordering=amount")
    expect(
      await screen.findByRole("combobox", { name: "Sort by" }),
    ).toHaveValue("amount")
    expect(
      screen.getByRole("button", { name: "Sort ascending" }),
    ).toBeInTheDocument()
  })

  it("puts the title and Add transaction in one header row", async () => {
    result([row])
    renderAt()
    expect(
      screen.getByRole("heading", { level: 1, name: "Transactions" }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Add transaction" }),
    ).toBeInTheDocument()
  })
```

(c) in `transaction-filters.test.tsx`, add `within` and `EMPTY_TRANSACTIONS_FILTERS` uses as needed and append to `describe("TransactionsFilterPanel", …)`:

```tsx
  it("turns 'Recurring only' on", async () => {
    const setFilters = vi.fn()
    render(
      <TransactionsFilterPanel
        filters={EMPTY_TRANSACTIONS_FILTERS}
        setFilters={setFilters}
        categories={[]}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const toggle = await screen.findByRole("switch", { name: "Recurring only" })
    expect(toggle).not.toBeChecked()
    await userEvent.click(toggle)
    const update = setFilters.mock.calls[0][0] as (
      f: TransactionsFilters,
    ) => TransactionsFilters
    expect(update(EMPTY_TRANSACTIONS_FILTERS).recurring).toBe(true)
  })

  it("turns 'Recurring only' off to no filter", async () => {
    const setFilters = vi.fn()
    const on = { ...EMPTY_TRANSACTIONS_FILTERS, recurring: true }
    render(
      <TransactionsFilterPanel
        filters={on}
        setFilters={setFilters}
        categories={[]}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const toggle = await screen.findByRole("switch", { name: "Recurring only" })
    expect(toggle).toBeChecked()
    await userEvent.click(toggle)
    const update = setFilters.mock.calls[0][0] as (
      f: TransactionsFilters,
    ) => TransactionsFilters
    expect(update(on).recurring).toBeNull()
  })

  it("shows the switch off for an old recurring=false link, still counted", async () => {
    render(
      <TransactionsFilterPanel
        filters={{ ...EMPTY_TRANSACTIONS_FILTERS, recurring: false }}
        setFilters={vi.fn()}
        categories={[]}
      />,
    )
    expect(screen.getByRole("button", { name: /Filters/ })).toHaveTextContent("1")
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    expect(
      await screen.findByRole("switch", { name: "Recurring only" }),
    ).not.toBeChecked()
  })

  it("groups min and max under Amount range", async () => {
    render(
      <TransactionsFilterPanel
        filters={EMPTY_TRANSACTIONS_FILTERS}
        setFilters={vi.fn()}
        categories={[]}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const group = await screen.findByRole("group", { name: "Amount range" })
    expect(within(group).getByLabelText("Min")).toBeInTheDocument()
    expect(within(group).getByLabelText("Max")).toBeInTheDocument()
  })
```

If another test in either file finds the amount inputs by "Min amount" / "Max amount", change it to "Min" / "Max".

- [ ] **Step 2: Run them to verify they fail**

Run (from `web-app/`): `pnpm vitest run apps/web/src/components/transactions`
Expected: the new tests FAIL ("Sort by" combobox, the switch and the "Amount range" group do not exist; the `<h1>` is in `page.tsx`).

- [ ] **Step 3: The sort control** — replace the whole of `transactions-sort-select.tsx`:

```tsx
"use client"

import { ArrowDown, ArrowUp } from "lucide-react"
import type { ListTransactionsOrdering } from "@app/api-client/types"
import { FilterSelect } from "@app/data-table/filters/filter-panel"
import { Button } from "@app/ui/button"

const FIELDS = [
  { value: "date", label: "Date" },
  { value: "amount", label: "Amount" },
  { value: "merchant", label: "Merchant" },
] as const
type SortField = (typeof FIELDS)[number]["value"]

const toOrdering = (field: SortField, desc: boolean) =>
  `${desc ? "-" : ""}${field}` as ListTransactionsOrdering

/**
 * Legacy's sort: a field and a direction, on every screen size. It reads and
 * writes the same `ordering` as a header click, so the two always agree. No
 * ordering is the list's default, newest first.
 */
export function TransactionsSortControl({
  ordering,
  onChange,
}: {
  ordering: ListTransactionsOrdering | null
  onChange: (ordering: ListTransactionsOrdering) => void
}) {
  const current = ordering ?? "-date"
  const desc = current.startsWith("-")
  const field = current.replace(/^-/, "") as SortField
  return (
    <div className="flex items-center gap-1">
      <FilterSelect
        aria-label="Sort by"
        className="w-auto"
        value={field}
        onChange={(e) => onChange(toOrdering(e.target.value as SortField, desc))}
      >
        {FIELDS.map((f) => (
          <option key={f.value} value={f.value}>
            {f.label}
          </option>
        ))}
      </FilterSelect>
      <Button
        variant="outline"
        size="icon-sm"
        aria-label={desc ? "Sort descending" : "Sort ascending"}
        onClick={() => onChange(toOrdering(field, !desc))}
      >
        {desc ? <ArrowDown /> : <ArrowUp />}
      </Button>
    </div>
  )
}
```

- [ ] **Step 4: The page header and toolbar** — in `transactions-table.tsx`:

(a) delete the `useIsMobile` import, the `const isMobile = useIsMobile()` line and the two comment lines above it ("Below 768px the table is cards…" / "no headers to click, so a select sorts."); change the import `{ TransactionsSortSelect }` to `{ TransactionsSortControl }`.

(b) wrap the returned `<>…</>` so the title and Add button form the first row — the fragment becomes:

```tsx
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Transactions</h1>
        <Button size="sm" onClick={() => setEditing("new")}>
          <PlusIcon />
          Add transaction
        </Button>
      </div>
      <ServerDataTable<TransactionResponse, unknown>
        {/* …every prop as before, except headerActions and toolbar below… */}
      />
      {/* …the dialogs, unchanged… */}
    </div>
```

(c) on `ServerDataTable`, `headerActions` becomes the sort control, and `toolbar` loses it:

```tsx
        headerActions={
          <TransactionsSortControl
            ordering={state.query.ordering}
            onChange={(ordering) => state.setSort(orderingToSorting(ordering))}
          />
        }
```

```tsx
        toolbar={
          <>
            <TableSearchInput
              value={state.search}
              onChange={state.setSearch}
              placeholder="Search merchants"
            />
            <TransactionsFilterPanel
              filters={state.filters}
              setFilters={state.setFilters}
              categories={categories}
            />
          </>
        }
```

(d) `page.tsx` becomes:

```tsx
import { TransactionsTable } from "@/components/transactions/transactions-table"

export default function TransactionsPage() {
  return <TransactionsTable />
}
```

- [ ] **Step 5: The filter contents** — in `transaction-filters.tsx`, import `FilterSection` alongside `FilterPanel` (drop `FilterField` and `FilterSelect` from that import if nothing else uses them), add `import { Label } from "@app/ui/label"` and `import { Switch } from "@app/ui/switch"`, and replace everything after `<FilterCheckboxGroup … />` inside `<FilterPanel>` with:

```tsx
      <FilterSection title="Amount range">
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label
              htmlFor="transactions-amount-min"
              className="text-xs font-normal text-muted-foreground"
            >
              Min
            </Label>
            <Input
              id="transactions-amount-min"
              type="number"
              step="0.01"
              inputMode="decimal"
              value={filters.amountMin ?? ""}
              onChange={(e) =>
                setFilters((f) => ({ ...f, amountMin: e.target.value || null }))
              }
            />
          </div>
          <div className="space-y-1">
            <Label
              htmlFor="transactions-amount-max"
              className="text-xs font-normal text-muted-foreground"
            >
              Max
            </Label>
            <Input
              id="transactions-amount-max"
              type="number"
              step="0.01"
              inputMode="decimal"
              value={filters.amountMax ?? ""}
              onChange={(e) =>
                setFilters((f) => ({ ...f, amountMax: e.target.value || null }))
              }
            />
          </div>
        </div>
      </FilterSection>
      <div className="flex items-center justify-between gap-4">
        <div>
          <Label htmlFor="transactions-recurring">Recurring only</Label>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Show only recurring transactions
          </p>
        </div>
        <Switch
          id="transactions-recurring"
          checked={filters.recurring === true}
          onCheckedChange={(on) =>
            setFilters((f) => ({ ...f, recurring: on ? true : null }))
          }
        />
      </div>
```

The `activeCount` helper and `TransactionsFilterChips` stay as they are: a `recurring: false` from an old URL still counts and keeps its "Not recurring" chip. If `getByRole("switch", { name: "Recurring only" })` does not resolve through the `Label` (Base UI's switch is a `<span role="switch">`), give the `Label` an `id="transactions-recurring-label"` and the `Switch` `aria-labelledby="transactions-recurring-label"` — `transaction-form-dialog.tsx` uses the same `Switch` + `Label htmlFor` pair, so check how its test finds the switch first.

- [ ] **Step 6: Run the tests**

Run: `pnpm vitest run apps/web/src/components/transactions`
Expected: all PASS.

- [ ] **Step 7: Docs** — in `docs/product/features/transactions.md` §2, replace the **Filter** and **Sort** bullets with:

```md
- **Filter** by date range (shortcuts: today, this week, this month, last month, or a
  custom range), by category (one or several), by amount range and to recurring only.
- **Sort** by date, amount or merchant, ascending or descending, from the sort control at
  the right of the toolbar — on every screen size. On desktop a column header sorts too;
  the control shows whatever was chosen last.
```

In `data-tables.md`, in the **Phone cards** bullet, replace "and a list that sorts adds its own select to `toolbar` when `useIsMobile()` is true, writing through" with "and a list that sorts needs a control of its own — transactions puts one in `headerActions` on every screen size — writing through".

- [ ] **Step 8: Gate and commit**

Run (from `web-app/`): `pnpm type-check && pnpm test`, then from the repo root `make check-web`.
Expected: all exit 0.

```bash
git add web-app/apps/web docs/product/features/transactions.md .claude/skills/web-app-patterns/references/data-tables.md
git commit -m "feat(transactions): legacy's header row, sort control and filter sheet contents"
```

---

### After the tasks (controller)

1. **Browser pass** on the slot-1 stack (`localhost:3010/transactions`, signed in as `dev-alice`), at 1440×900 and 390×844: retake `ours-1-table`, `ours-2-filters`, `ours-3-bulk` into `.playwright-mcp/compare/`, rebuild the three side-by-sides against the legacy shots, and walk Review Focus 1, 2 and 5 by eye.
2. **Whole-branch review** of the three commits on the most capable model.
3. In the PR that lands this (PR #12): delete this plan and its spec; their lasting facts are in `data-tables.md` and the feature doc. Update the PR body's Web section (filter sheet, floating bar, table frame, sort control) and push.

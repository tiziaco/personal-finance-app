# FiltersBar Refactor Design

**Date:** 2026-03-16
**Branch:** improve-transaction-management
**File:** `web-app/src/components/transactions/filters-bar.tsx`

## Overview

Refactor `FiltersBar` from an inline card-based filter panel to a toolbar + side-sheet pattern, based on a reference design. The component stays fully controlled (all filter state owned by the parent `TransactionsPage`) with live filtering — no draft buffering.

## Layout

The card wrapper (`bg-card rounded-xl border p-4`) is removed. `FiltersBar` renders a flat `div` directly on the page background.

**Toolbar row (single line):**
```
[Search input]  [Filters button (+ badge)]  [Clear button]  ───────  [Sort select]  [Sort direction toggle]
```

- Search, Filters button, and Clear button on the left
- Sort controls pushed to the right via `ml-auto`
- Clear button only visible when `hasActiveFilters === true`

## Filters Button

- Uses shadcn `Button` variant `outline` by default
- Switches to variant `default` (primary) when the sheet is open OR `activeCount > 0`
- When `activeCount > 0`, renders a small inline `<span>` badge as a sibling to the button text inside the `<Button>`: `<Button>Filters <span>{activeCount}</span></Button>`. The span is a rounded pill styled with `bg-primary-foreground/20 text-primary-foreground`.
- `activeCount` computed internally from props: counts how many of the four filter groups have a non-default value — date range (1 if `dateFrom` OR `dateTo` is set), category (1 if set), amount range (1 if `amountMin` OR `amountMax` is set), recurring (1 if `isRecurring !== undefined`). Maximum value is 4.

## Sheet (Right Drawer)

Uses the existing `Sheet` component (`side="right"`, default width `w-3/4 sm:max-w-sm` ≈ 384 px). The sheet is **controlled**: `<Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>`. `drawerOpen` is local state. The Filters button calls `setDrawerOpen(true)` directly — no `SheetTrigger` is used, so the button variant can derive from `drawerOpen`. Filters apply live — every change calls the corresponding prop callback immediately.

**Sheet structure:**
- `<SheetContent side="right" showCloseButton>` — `showCloseButton` renders an absolutely-positioned X button inside the popup (not inside the header)
- `<SheetHeader>` — contains `<SheetTitle>Filters</SheetTitle>` and, when `activeCount > 0`, a `<SheetDescription>{activeCount} active</SheetDescription>`
- Sheet body — scrollable `div` with sections separated by `<Separator />`
- No Sheet footer (no Apply button)

**Sheet body sections:**

1. **Date range** — The `Calendar` component is rendered **inline** (no nested `Popover`) directly in the sheet body. This avoids portal/z-index conflicts from nesting a base-ui Dialog (Popover) inside another base-ui Dialog (Sheet). The two-click range logic (`handleRangeSelect`, `awaitingEndRef`) is preserved, but `calendarOpen` state and the `setCalendarOpen(false)` call inside `handleRangeSelect` are removed — the calendar is always visible, so there is no popover to open/close. The trigger label from the toolbar version is replaced by a static section label. The calendar renders in `mode="range"` with `selected={selectedRange}`.
2. **Category** — existing shadcn `Select` with `CATEGORY_OPTIONS`
3. **Amount range** — two shadcn `Input` fields (Min €, Max €) side by side
4. **Recurring only** — shadcn `Switch` + label/description ("Show only recurring transactions")

**Sheet close behavior:** When the Sheet closes (`onOpenChange(false)`), `awaitingEndRef.current` and `firstClickDateRef.current` are reset — the same reset logic currently in `handleOpenChange` applied when the calendar popover closes. This prevents a stale "awaiting end date" state if the user closes the sheet mid-selection.

**Sheet footer:** Not used (no Apply button — live filtering).

## Sort Controls (Toolbar)

Remain outside the Sheet — sort is used frequently and should always be one click away.

- `Select` for sort field (Date / Amount / Merchant) — existing shadcn `Select`
- `Button` icon-only for sort direction toggle (`ArrowUp` / `ArrowDown`) — existing shadcn `Button`

## Props Interface

No changes to `FiltersBarProps`. The interface remains fully controlled with individual value/callback pairs for each filter, plus `hasActiveFilters` and `onClearAll`.

## Dependencies

- **Install:** `Switch` shadcn component (currently absent from `web-app/src/components/ui/`)
- **Existing (no changes needed):** `Sheet`, `Button`, `Input`, `Select`, `Calendar`, `Popover`, `Separator`

## What Does Not Change

- All filter logic in `TransactionsPage` (state, `updateFilter`, `clearAllFilters`)
- The Calendar date range two-click UX (`handleRangeSelect`, `awaitingEndRef`)
- `FiltersBarProps` type
- How `FiltersBar` is consumed in `page.tsx`

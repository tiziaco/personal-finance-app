# Transactions: the legacy look — design

**Date:** 14 Oct 2026 · **Branch:** `feat/transactions` (PR #12, roadmap step 2)
**Reference:** pf-legacy's transactions page — `web-app/src/components/transactions/filters-bar.tsx`,
`transactions-table.tsx`, `components/ui/data-table-bulk-actions.tsx` — and side-by-side
screenshots taken 14 Oct 2026 with the same 1,038 rows in both apps.

## 1. Why

Step 2 shipped `/transactions` on the template's shared table. Next to legacy, three things
read worse: the table has no frame and small type, the filters drop down from a button (and
open over the sidebar, with 8 of 20 categories visible before an inner scroll), and the bulk
bar is a flat strip above the table. The toolbar also wraps Filters onto a second line. This
pass brings legacy's layout back while keeping what step 2 added.

## 2. Decisions (made with the user, 14 Oct 2026)

| # | Decision |
|---|---|
| D1 | **Sort:** column headers keep sorting on desktop, *and* legacy's control — a field select (Date, Amount, Merchant) plus an ↑/↓ direction button — sits at the right of the toolbar on every screen size. Both read and write the one `ordering` URL key, so they agree. It replaces the phone-only six-option select. |
| D2 | **Filters:** a right-hand sheet with legacy's layout — a header with the count of active filters, ruled sections with uppercase titles, "Clear all filters" at the bottom while any is active. The contents stay step 2's: date presets and mode, several categories as checkboxes (all 20 visible; the sheet scrolls), min/max amount side by side under one "Amount range" title. Chips stay under the toolbar. Full width on a phone. |
| D3 | **Recurring:** legacy's "Recurring only" switch replaces the Any / Recurring / Not recurring select. On → `recurring=true`; off → no filter. A `recurring=false` URL still filters and shows its chip; the switch shows off. |
| D4 | **Table:** every `@app/data-table` table sits in a card (`rounded-xl border bg-card shadow-sm`), with uppercase muted header labels on a tinted strip, 14px body text and roomier cells. Phone cards are unchanged. |
| D5 | **Bulk bar:** a floating pill — count badge, "selected", the page's actions, × — centred under the table and kept in view at the bottom of the viewport while the table scrolls past it. Desktop only, as before. |
| D6 | **Page header and toolbar:** "Transactions" and "Add transaction" share the top row, as in legacy. Below: search and Filters on the left, the sort control on the right, on one row from 640px up. |

## 3. Out of scope

The theme — legacy's teal accent, grey-green page background, pill-shaped controls and font.
It changes every page, so it is its own decision, not part of step 2. Also out: legacy's
calendar date-range picker, per-section "Clear" links, and "Import CSV" (step 4).

## 4. Where the facts land

- `.claude/skills/web-app-patterns/references/data-tables.md` — the sheet, the floating bar,
  the card frame, and a sort control a list adds for itself.
- `docs/product/features/transactions.md` §2 — "recurring only", and the sort control on
  every screen size.

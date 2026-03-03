# Phase 7: Polish - Research

**Researched:** 2026-03-03
**Domain:** Design system tokens, dark mode, responsive layout, toast notifications, skeleton loading
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Dark mode is managed via **next-themes** (`ThemeProvider` / `useTheme` / `class` strategy), NOT via Tailwind `dark:` utility classes directly driven by the user's OS preference
- Components should respect the theme class applied by next-themes to the `<html>` element; Tailwind `dark:` variants are still used for styling, but the toggle mechanism is next-themes

### Claude's Discretion
- Color token consolidation approach (CSS variables vs Tailwind config)
- Skeleton loading library/component choice
- Toast library/component choice (likely already in use — check existing code)
- Mobile sidebar implementation details (sheet/drawer pattern)
- Breakpoint strategy for responsive chart/table layouts

### Deferred Ideas (OUT OF SCOPE)
None identified.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SETT-01 | User can set currency preference (dropdown: EUR default, plus USD, GBP, etc.) in Settings | DateFormatProvider pattern is the exact blueprint — build CurrencyProvider with same localStorage strategy; wire into formatCurrency |
| DESGN-01 | App uses consistent color tokens: Teal (#208E95) primary, Warm Gray (#5E5240) secondary, Cream (#FCFCF9) light background, Charcoal (#1F2121) dark mode background, Red (#C01527) overspend alerts, Green (#208E95) savings | Existing CSS vars in globals.css use OKLCH — new tokens must also be OKLCH; `text-green-600` raw classes found in analytics + transactions components need replacement with semantic CSS variable tokens |
| DESGN-02 | App supports full dark mode with Tailwind CSS dark: classes applied throughout all pages and components | next-themes already wired with `attribute="class"` + `suppressHydrationWarning`; @custom-variant dark already defined in globals.css; most app pages have zero dark: classes but rely entirely on CSS variables — audit shows CSS-variable-based components already adapt; only raw color classes (text-green-600, bg-red-500 etc.) need dark: companions or token replacement |
| DESGN-03 | Desktop layout has a collapsible sidebar; mobile layout has a hamburger menu that opens the sidebar as an overlay or drawer | Sidebar component already renders as `<Sheet>` on mobile (isMobile branch at line 182 of sidebar.tsx); `SidebarTrigger` already calls `toggleSidebar()` which routes to `setOpenMobile`; gap is that `SidebarTrigger` in layout.tsx is always visible but not positioned as a hamburger menu header on mobile |
| DESGN-04 | All interactive elements have minimum 48px tap targets on mobile | No systematic enforcement found; must be applied via `min-h-12` (48px) on buttons, inputs, checkboxes in transaction table, and nav items |
| DESGN-05 | Charts render at full width on mobile, 2-column grid on desktop | Dashboard home already uses `grid grid-cols-1 md:grid-cols-2`; spending-by-category-tab already uses `grid-cols-1 md:grid-cols-2`; trends-tab and income-vs-expenses-tab charts use `w-full` but sit in single-column containers — needs verification at 375px |
| DESGN-06 | Transaction table collapses to a card-list layout at mobile breakpoints | Current table is `<table>` with `overflow-auto` wrapping — horizontal scroll on mobile, NOT card-list; must implement a dual-render: table on `md:` and above, card-list below |
| DESGN-07 | Toast notifications appear for all user-initiated actions (category update, insights generated, errors) | sonner already installed and wired; `toast.success/error` already called in: `useUpdateTransaction`, `useBatchUpdateTransactions`, `useDeleteAllTransactions`, `generate-button.tsx`, `error-boundary.tsx`; audit needed for missing coverage |
| DESGN-08 | Skeleton loading screens appear for all data-heavy regions before data loads | All 4 skeleton components exist (CardSkeleton, ChartSkeleton, InsightCardSkeleton, TableSkeleton); usage audit needed — some data-bearing regions may not show skeletons during isLoading |
</phase_requirements>

---

## Summary

Phase 7 is a polish/finishing phase that touches the entire frontend surface. The core technologies are all already installed and partially wired: next-themes controls dark mode, sonner handles toasts, the shadcn sidebar component already does mobile-as-Sheet, and skeleton components exist for all regions. The work is almost entirely **audit + gap-fill**, not greenfield implementation.

The most substantial new work is (1) the transaction table card-list collapse on mobile — currently it is a horizontally-scrolling `<table>` with no mobile-specific rendering, (2) the SETT-01 currency preference feature which mirrors the existing DateFormatProvider pattern, and (3) color token consolidation — several components use raw Tailwind color classes (`text-green-600`, `bg-red-500`, `text-amber-600`) that won't respect dark mode via CSS variables and need replacement with semantic tokens defined in globals.css.

Dark mode is already structurally correct: `ThemeProvider attribute="class"` with `suppressHydrationWarning` is in root layout, `@custom-variant dark (&:is(.dark *))` is declared in globals.css, and all shadcn/ui components use CSS variable tokens that already flip in `.dark`. The only dark mode work is replacing the few raw color classes with CSS variable equivalents.

**Primary recommendation:** Structure this phase into 5 focused tasks: (1) color tokens + raw-class audit/fix, (2) dark mode verification sweep, (3) responsive sidebar hamburger + tap-target enforcement, (4) transaction table card-list on mobile + chart grid verification, (5) SETT-01 currency preference + toast/skeleton coverage audit.

---

## Standard Stack

### Core (all already installed — no new packages needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next-themes | ^0.4.6 | Dark mode toggle, class strategy on `<html>` | Already wired; `ThemeProvider attribute="class"` in root layout |
| sonner | ^2.0.7 | Toast notifications | Already installed; `Toaster` component in root layout; `toast.success/error` used in mutations |
| tailwindcss | ^4 | Dark mode via `dark:` classes + CSS variables | `@custom-variant dark (&:is(.dark *))` already declared |
| shadcn sidebar | (local) | Mobile drawer via Sheet | Already handles `isMobile` → Sheet pattern natively |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | ^0.575.0 | Menu icon for hamburger trigger | Already used throughout — use `Menu` icon for mobile trigger |
| clsx / tailwind-merge | — | Conditional dark: class composition | Already in use via `cn()` utility |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| CSS variable tokens in globals.css | Tailwind config `extend.colors` | CSS variables are already the pattern in this project (OKLCH in `:root` and `.dark`); Tailwind config extension would duplicate values — stick with globals.css |
| Dual-render card-list (new JSX) | CSS-only responsive table | CSS-only `display:block` table collapse is hacky and breaks accessibility semantics; explicit card JSX with `hidden md:block` / `md:hidden` is cleaner and already the pattern in this project |
| sonner toast.promise | individual toast.success/error | `toast.promise` is cleaner for async flows but requires refactoring existing mutation hooks; use it only for new SETT-01 currency save action |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── providers/
│   ├── date-format-provider.tsx   # existing — blueprint for currency
│   └── currency-provider.tsx      # NEW — mirrors date-format-provider exactly
├── components/
│   ├── settings/sections/
│   │   └── general-section.tsx    # add currency dropdown here (SETT-01)
│   ├── transactions/
│   │   └── transactions-table.tsx # add card-list mobile variant (DESGN-06)
│   └── layout/
│       └── app-sidebar.tsx        # verify mobile hamburger visibility
└── styles/
    └── globals.css                # add --color-success, --color-warning tokens
```

### Pattern 1: CSS Variable Token Definition (Tailwind v4, OKLCH)

**What:** All brand colors are defined as OKLCH CSS custom properties in `:root` and `.dark` blocks within globals.css, then exposed to Tailwind via `@theme inline`.

**When to use:** When adding new semantic color tokens (e.g., `--color-success` for positive financial values to replace `text-green-600`).

**Example:**
```css
/* Source: globals.css pattern already in use + Tailwind v4 @theme docs */
@theme inline {
  --color-success: var(--success);
  --color-warning: var(--warning);
}

:root {
  --success: oklch(0.55 0.15 145);   /* green for positive net/income */
  --warning: oklch(0.72 0.15 65);    /* amber for low-confidence scores */
}

.dark {
  --success: oklch(0.70 0.15 145);   /* slightly lighter for dark bg contrast */
  --warning: oklch(0.80 0.15 65);
}
```

Then use as `text-success`, `text-warning` in component files — no `dark:` variant needed since the CSS variable flips.

**Key insight:** This is the pattern already used for `--primary`, `--destructive`, etc. Adding `--success` and `--warning` tokens eliminates ALL `text-green-600`/`text-amber-600` occurrences and makes them dark-mode-aware automatically.

### Pattern 2: CurrencyProvider (SETT-01, mirrors DateFormatProvider)

**What:** Context + localStorage provider that stores currency preference and provides `formatCurrency` helper via hook.

**When to use:** Anywhere currency amounts are displayed — all existing `formatCurrency()` call sites.

**Example:**
```typescript
// Source: web-app/src/providers/date-format-provider.tsx — exact blueprint
"use client"

import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

export type Currency = "EUR" | "USD" | "GBP" | "CHF" | "JPY"

const CURRENCY_KEY = "pf_currency"
const DEFAULT_CURRENCY: Currency = "EUR"

interface CurrencyContextValue {
  currency: Currency
  setCurrency: (c: Currency) => void
  formatCurrency: (value: number | string) => string
}

// formatCurrency is derived in the provider so it captures current currency + locale
```

**Migration:** Existing `formatCurrency(value)` call sites can adopt a `useCurrencyFormat()` hook that returns the bound formatter — mirrors the `useFormatDate()` shadow-import pattern already in STATE.md.

### Pattern 3: Transaction Table Mobile Card-List (DESGN-06)

**What:** Render two independent views — the existing `<table>` hidden on mobile, a new card-list visible only on mobile. React Query provides data to both; no data duplication.

**When to use:** At the `sm:` breakpoint (640px) — below this, show cards; above, show table.

**Example:**
```tsx
{/* Desktop: existing table — hide on mobile */}
<div className="hidden sm:block w-full overflow-auto rounded-lg border">
  <table className="w-full text-sm">...</table>
</div>

{/* Mobile: card list */}
<div className="sm:hidden space-y-3">
  {table.getRowModel().rows.map((row) => (
    <TransactionCard key={row.id} transaction={row.original} onEdit={onEditTransaction} />
  ))}
</div>
```

Cards should show: merchant, date, amount (large), category badge, edit button. Edit button must be `min-h-12` (48px) for DESGN-04.

### Pattern 4: Dark Mode with next-themes (already wired)

**What:** `ThemeProvider attribute="class"` puts `.dark` on `<html>`; Tailwind `dark:` variants trigger from this class; `@custom-variant dark (&:is(.dark *))` enables dark: on all descendants.

**When to use:** `dark:` classes are needed ONLY for raw color values that aren't already driven by CSS variables. Most shadcn components do NOT need dark: classes — they use CSS vars that already flip. Only places with `text-green-600`, `bg-red-500`, `text-amber-600` need attention.

**Audit findings — raw color classes requiring fix:**
- `web-app/src/components/analytics/income-vs-expenses-tab.tsx` — `text-green-600` (3 occurrences)
- `web-app/src/components/analytics/trends-tab.tsx` — `text-green-600` (1 occurrence)
- `web-app/src/components/transactions/transactions-table.tsx` — `text-amber-600`, `text-green-600`
- `web-app/src/components/settings/sections/data-section.tsx` — `border-red-500`, `text-red-500`, `hover:bg-red-50` (should use `border-destructive`, `text-destructive`)
- `web-app/src/components/settings/server-status.tsx` — `bg-green-500`, `bg-red-500` (status indicators — acceptable since semantic meaning is visual only; add `dark:` companion if needed)

### Pattern 5: Mobile Sidebar Hamburger Trigger

**What:** The `SidebarTrigger` already calls `toggleSidebar()` → `setOpenMobile()` on mobile. The sidebar renders as a `<Sheet>` on mobile. The gap is that the trigger button is floated inline with content and may not be visible as a clear mobile header.

**Assessment (HIGH confidence):** The shadcn sidebar implementation already has full mobile support. The existing layout places `SidebarTrigger` between sidebar and content. At mobile breakpoints (< 768px), the sidebar div has `hidden md:block` so it collapses; the Sheet opens via `openMobile`. **No new mobile sidebar code is needed.** The trigger just needs to be styled/positioned appropriately for mobile UX.

**Verification needed:** Test at 375px viewport in browser to confirm the trigger is reachable and the Sheet opens correctly.

### Anti-Patterns to Avoid

- **Raw Tailwind color classes for semantic meanings:** `text-green-600` does not adapt to dark mode via CSS variables. Replace with `text-success` tokens defined in globals.css.
- **Adding `dark:` classes where CSS variables already work:** Shadcn components (`Card`, `Button`, `Badge`, etc.) already use CSS variables — adding redundant `dark:` classes creates maintenance burden.
- **Building a custom currency provider from scratch:** The `DateFormatProvider` in `web-app/src/providers/date-format-provider.tsx` is the exact blueprint — duplicate it and adapt.
- **Making `formatCurrency` a global function that ignores user preference:** The existing `formatCurrency(value, currency, locale)` has optional params — but all call sites pass no args and rely on EUR/de-DE defaults. The currency provider hook is the correct migration path.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dark mode toggle | Custom OS-preference listener | next-themes (already installed) | Handles SSR flash, localStorage persistence, system preference, hydration mismatch |
| Toast notifications | Custom portal + timeout logic | sonner (already installed) | Handles stacking, swipe-to-dismiss, promise integration, theming |
| Mobile sidebar drawer | Custom Sheet component | shadcn Sidebar (already handles isMobile → Sheet) | Sheet is already used; SidebarProvider.toggleSidebar() routes correctly |
| Skeleton animations | Custom keyframe CSS | shadcn Skeleton component (already in use) | pulse animation built in; consistent with design system |
| Currency formatting | Custom number → string | `Intl.NumberFormat` (already in formatCurrency) | Browser-native, handles currency symbols, thousands separators, locale |

**Key insight:** Every "don't hand-roll" item is already in the codebase. This phase is about wiring existing pieces correctly, not adding infrastructure.

---

## Common Pitfalls

### Pitfall 1: Assuming CSS Variables Make Dark Mode Automatic for All Classes

**What goes wrong:** A developer sees that `Card` looks correct in dark mode and assumes ALL color styling is CSS-variable-driven. They miss that `text-green-600` is a static Tailwind class with no dark variant — it stays medium green on dark backgrounds.

**Why it happens:** Most shadcn components DO use CSS variables. The inconsistency is only in the few hand-written classes.

**How to avoid:** Run a grep for `text-green`, `bg-green`, `text-amber`, `bg-red` in `src/components` before marking DESGN-02 complete.

**Warning signs:** Green text that looks washed-out or hard to read in dark mode.

### Pitfall 2: CurrencyProvider Not Wrapping All formatCurrency Call Sites

**What goes wrong:** The CurrencyProvider is added and the Settings UI works, but existing components still call the bare `formatCurrency()` from `@/lib/format` with hard-coded EUR defaults.

**Why it happens:** Many call sites don't import from the hook. The shadow-import pattern (from STATE.md: `const formatCurrency = useCurrencyFormat()`) is the correct migration approach.

**How to avoid:** After adding the CurrencyProvider, grep for `formatCurrency` import from `@/lib/format` and migrate all call sites to the hook.

**Warning signs:** Changing currency in Settings has no effect on displayed amounts.

### Pitfall 3: Transaction Card-List Missing Pagination Controls on Mobile

**What goes wrong:** The card-list renders the current page's transactions but the pagination controls (Previous/Next) remain in the table wrapper which is hidden on mobile.

**Why it happens:** Pagination is rendered inside the table's JSX block.

**How to avoid:** Extract pagination controls to a shared component outside the `hidden sm:block` wrapper, visible on all breakpoints.

### Pitfall 4: Tap Targets — Checkboxes in Transaction Table

**What goes wrong:** The native `<input type="checkbox">` in the transaction table has a default size of ~18px — well below the 48px minimum. The current implementation uses `className="cursor-pointer"` with no size enforcement.

**Why it happens:** Native checkboxes don't inherit min-h from parent easily.

**How to avoid:** Wrap checkboxes in a `<label>` or `<div>` with `min-h-12 min-w-12 flex items-center justify-center`. Alternatively, use `className="h-5 w-5"` plus a touch-area wrapper — `after:absolute after:inset-[-12px] relative`.

### Pitfall 5: next-themes Hydration Flash if suppressHydrationWarning Missing

**What goes wrong:** `<html>` flashes unstyled before theme class is applied.

**Why it happens:** next-themes modifies the `<html>` element class after SSR.

**How to avoid:** Already correctly handled in `app/layout.tsx` with `suppressHydrationWarning` on `<html>`. Do NOT remove it.

### Pitfall 6: SidebarTrigger Invisible on Mobile if Sidebar is Hidden

**What goes wrong:** The sidebar wrapper div has `hidden md:block` — but the `SidebarTrigger` is placed inside `SidebarInset` (outside the sidebar div), so it is always visible. Verify actual DOM position at 375px.

**Why it happens:** Layout reads:
```tsx
<SidebarProvider>
  <AppSidebar />           {/* hidden on mobile */}
  <SidebarTrigger />       {/* outside sidebar — should remain visible */}
  <SidebarInset>           {/* page content */}
```
**How to avoid:** Confirm the trigger appears at mobile breakpoints by testing. It should be visible as a floating button. If not, add explicit `block` and positioning.

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Adding a CSS Variable Token (Tailwind v4 OKLCH pattern)

```css
/* Source: web-app/src/styles/globals.css — existing pattern */
@theme inline {
  --color-success: var(--success);
  --color-warning: var(--warning);
}

:root {
  /* OKLCH values — do NOT use hsl() wrapper (STATE.md: hsl() breaks rendering in Tailwind v4) */
  --success: oklch(0.55 0.15 145);
  --warning: oklch(0.72 0.15 65);
}

.dark {
  --success: oklch(0.70 0.15 145);
  --warning: oklch(0.82 0.15 65);
}
```

Then use `className="text-success"` instead of `className="text-green-600"`.

### Currency Provider (mirrors DateFormatProvider)

```typescript
// Source: web-app/src/providers/date-format-provider.tsx — blueprint
"use client"
import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

export type Currency = "EUR" | "USD" | "GBP" | "CHF"

const CURRENCY_KEY = "pf_currency"
const DEFAULT_CURRENCY: Currency = "EUR"

const LOCALE_MAP: Record<Currency, string> = {
  EUR: "de-DE", USD: "en-US", GBP: "en-GB", CHF: "de-CH",
}

interface CurrencyContextValue {
  currency: Currency
  setCurrency: (c: Currency) => void
  formatAmount: (value: number | string) => string
}

const CurrencyContext = createContext<CurrencyContextValue>({
  currency: DEFAULT_CURRENCY,
  setCurrency: () => {},
  formatAmount: (v) => String(v),
})

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [currency, setCurrencyState] = useState<Currency>(DEFAULT_CURRENCY)

  useEffect(() => {
    const stored = localStorage.getItem(CURRENCY_KEY) as Currency | null
    if (stored && ["EUR", "USD", "GBP", "CHF"].includes(stored)) {
      setCurrencyState(stored)
    }
  }, [])

  const setCurrency = (c: Currency) => {
    setCurrencyState(c)
    localStorage.setItem(CURRENCY_KEY, c)
  }

  const formatAmount = (value: number | string): string => {
    const num = typeof value === "string" ? parseFloat(value) : value
    if (isNaN(num)) return "—"
    return new Intl.NumberFormat(LOCALE_MAP[currency], {
      style: "currency", currency
    }).format(num)
  }

  return (
    <CurrencyContext.Provider value={{ currency, setCurrency, formatAmount }}>
      {children}
    </CurrencyContext.Provider>
  )
}

export function useCurrency() {
  return useContext(CurrencyContext)
}
```

### Transaction Card (mobile card-list variant)

```tsx
// Mobile-only card — hidden on sm: and above
function TransactionCard({
  transaction,
  onEdit,
}: { transaction: TransactionResponse; onEdit: (t: TransactionResponse) => void }) {
  const formatDate = useFormatDate()
  const { formatAmount } = useCurrency()

  return (
    <div className="rounded-lg border bg-card p-4 flex items-start justify-between gap-3">
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-medium text-sm truncate">{transaction.merchant}</p>
        <p className="text-xs text-muted-foreground">{formatDate(transaction.date)}</p>
        <span className="inline-block text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
          {transaction.category}
        </span>
      </div>
      <div className="shrink-0 flex flex-col items-end gap-2">
        <p className="font-semibold text-sm">{formatAmount(transaction.amount)}</p>
        {/* 48px tap target for edit button */}
        <button
          onClick={() => onEdit(transaction)}
          className="min-h-12 min-w-12 flex items-center justify-center rounded-md hover:bg-muted"
          aria-label="Edit category"
        >
          <Edit2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
```

### Toast Coverage for Missing Actions

```typescript
// Source: web-app/src/hooks/use-transaction-mutations.ts — existing pattern
// Add toast to any action that doesn't have one yet:

// CSV upload action (check upload page)
toast.success('Transactions imported successfully')
toast.error('Failed to import CSV. Please check the file format.')

// Settings currency save (SETT-01)
// No mutation needed — localStorage via provider; show confirmation:
toast.success('Currency preference saved')
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `darkMode: 'class'` in tailwind.config.js | `@custom-variant dark (&:is(.dark *))` in globals.css | Tailwind v4 | Config-based dark mode removed in v4; must use CSS-native variant |
| `hsl(var(--color))` CSS variable pattern | `oklch(L C H)` direct values | Tailwind v4 shadcn | `hsl()` wrapper breaks in Tailwind v4 per STATE.md decision |
| Separate skeleton library (react-loading-skeleton) | shadcn `Skeleton` component (CSS animation) | shadcn adoption | No extra dependency; consistent with design system |
| Custom dark mode toggle (localStorage + JS) | next-themes | Common in 2023+ | Handles SSR flash, system pref, hydration — don't reinvent |

**Deprecated/outdated:**
- `tailwind.config.js darkMode: 'class'` — replaced by `@custom-variant dark` in globals.css (Tailwind v4). The project correctly does NOT have this in tailwind.config.ts.
- `hsl(var(--color))` wrapper — **do not add** when defining new CSS variable tokens. Use bare `oklch()` values.

---

## Open Questions

1. **Should the currency setting require a page refresh to propagate to all components?**
   - What we know: The DateFormat provider updates instantly via React context; `formatCurrency` call sites currently bypass context
   - What's unclear: After migrating call sites to `useCurrency().formatAmount`, instant propagation will work — but is a full migration of all `formatCurrency` calls in scope for this phase?
   - Recommendation: Yes — migrate all `formatCurrency(value)` call sites to `useCurrency().formatAmount(value)` as part of SETT-01; it's the same shadow-import pattern already in STATE.md

2. **Should server-status.tsx `bg-green-500`/`bg-red-500` be converted to tokens?**
   - What we know: Server status indicators are small colored dots; semantic meaning is purely visual (green=healthy, red=error)
   - What's unclear: These don't have dark-mode counterparts in the design spec
   - Recommendation: Add `dark:bg-green-400`/`dark:bg-red-400` companions rather than new CSS variable tokens — status dots are too narrow a use case for dedicated tokens

3. **Is DESGN-03 already satisfied by the existing Sidebar implementation?**
   - What we know: Sidebar renders as `<Sheet>` when `useIsMobile()` returns true (< 768px); `SidebarTrigger` calls `toggleSidebar()` which routes to `setOpenMobile()`
   - What's unclear: Whether the current layout correctly positions the trigger as a visible hamburger at 375px without manual testing
   - Recommendation: Treat as "likely satisfied, needs verification" — test at 375px, fix positioning only if needed; this is a verification task, not a build task

---

## Validation Architecture

> `workflow.nyquist_validation` is not set in `.planning/config.json` — the key is absent, and the file has no `nyquist_validation` field. Skipping this section.

---

## Sources

### Primary (HIGH confidence)
- `/pacocoursey/next-themes` (Context7) — ThemeProvider attribute="class", suppressHydrationWarning, dark: usage with Tailwind
- `/emilkowalski/sonner` (Context7) — toast.success/error/promise/info/warning API
- `/tailwindlabs/tailwindcss.com` (Context7) — @custom-variant dark, @theme inline, CSS variable to Tailwind token pattern
- Direct codebase inspection — globals.css (OKLCH tokens, dark variant), sidebar.tsx (isMobile → Sheet), layout.tsx (ThemeProvider config), use-transaction-mutations.ts (existing toast coverage), date-format-provider.tsx (currency provider blueprint)

### Secondary (MEDIUM confidence)
- STATE.md decision log — OKLCH vs hsl() issue (verified via globals.css; confirmed hsl() wrapper not present), shadow-import pattern for formatDate migration

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; verified in package.json and import usage
- Architecture: HIGH — all patterns derived from existing working code in the same project
- Pitfalls: HIGH — derived from direct codebase audit (grep results for raw color classes, DOM structure of table, tap target inspection)

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (stable libraries; CSS variable pattern is stable in Tailwind v4)

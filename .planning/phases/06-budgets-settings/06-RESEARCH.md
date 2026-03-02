# Phase 6: Budgets + Settings - Research

**Researched:** 2026-03-02
**Domain:** Next.js app routing, React Context, localStorage persistence, shadcn/base-ui modals, settings architecture
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Budgets page**
- Simple "Coming Soon" placeholder page at `/budgets`
- Add as a nav item in the sidebar (alongside Home, Transactions, Analytics, Insights)
- Minimal design: prominent "Coming Soon" message + brief description of what budgets will offer
- No CTA (no "notify me" or other interactivity)

**Settings: General section**
- Keep existing theme selector exactly as-is (already functional via `next-themes` + `useTheme()`)
- Do NOT migrate to Tailwind `dark:` classes — current implementation is clean and working
- Add date format preference below the theme selector
- Date format stored in **localStorage** (no backend required)
- Exposed via React Context so `formatDate()` in `lib/format.ts` reads the user's choice
- Formats offered: DD/MM/YYYY (default, current de-DE), MM/DD/YYYY (US), YYYY-MM-DD (ISO)

**Settings: Notifications section (new)**
- New section added to settings dialog sidebar nav
- Contains non-functional toggle placeholders: email alerts, budget alerts, newsletter
- Clearly marked as "Coming Soon" — no real functionality
- Follows the same `SettingSection` + `Label` pattern as other sections

**Settings: Integrations section**
- Remove entirely — it's a template leftover (Google Drive, Slack) with no relevance to the finance app

**Settings: Data section**
- Keep section name as "Data"
- Add: "Delete All Transactions" with confirmation modal; after deletion stay on same page (empty state appears)
- Keep existing "Delete All Chats" and Memory Usage blocks — user plans to use them soon
- Update destructive button label from "Delete All Chats" to "Delete All Transactions" for the new action (keep the old chats one)

**Currency preference**
- Skip entirely for this phase — no backend storage or currency converter to support it
- `formatCurrency()` remains hardcoded to EUR/de-DE

### Claude's Discretion
- Confirmation modal design and copy for Delete All Transactions
- Exact layout and spacing of the date format selector
- Toast message wording after successful transaction deletion
- How the "Coming Soon" Notifications section is visually distinguished

### Deferred Ideas (OUT OF SCOPE)
- Currency preference — deferred until backend user profile or localStorage-only solution is justified; no currency converter in backend yet
- Functional notification preferences — out of scope; placeholder only in this phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BUDG-01 | User sees a Budgets page with a prominent "Coming Soon" message and brief description of what budgets will offer | New Next.js page at `/budgets` route; add nav item to `HUB_NAV` in `lib/hub-nav.ts`; no data fetching needed |
| SETT-01 | User can set currency preference (EUR default) — **DEFERRED per CONTEXT.md decisions** | `formatCurrency()` stays hardcoded; no implementation required this phase |
| SETT-02 | User can set date format preference (DD/MM/YYYY default, plus MM/DD/YYYY, YYYY-MM-DD) | React Context + localStorage pattern; wire to `formatDate()` in `lib/format.ts`; `Select` component in `GeneralSection` |
| SETT-03 | User can toggle theme between Light / Dark / System from Settings | Already implemented via `next-themes` + `useTheme()` in `GeneralSection` — verify only, no code changes needed |
| SETT-04 | User can delete all transactions from Settings (red button requiring confirmation modal) | `AlertDialog` from `@base-ui/react/alert-dialog` already wired in `components/ui/alert-dialog.tsx`; fetch all transaction IDs then `batchDeleteTransactions()` in batches of 100 (API limit); `queryClient.invalidateQueries` after; `sonner` toast |
| SETT-05 | User sees placeholder Notification Preferences toggles (email, budget alerts, newsletter — non-functional in v1) | New `notifications-section.tsx` file; add "notifications" nav item in `settings-dialog.tsx`; remove "integrations" nav item; use `SettingSection` + toggle-style UI with "Coming Soon" label |
</phase_requirements>

---

## Summary

Phase 6 is a low-complexity, high-clarity phase. There are no new libraries to install, no new backend endpoints to build, and no architectural departures from patterns already established in the codebase. Every building block is already in place: `AlertDialog` is wired, `sonner` toasts are in `layout.tsx`, `SettingSection` pattern is used for all existing sections, and `next-themes` / `useTheme()` already handle theme toggling.

The two substantive pieces of work are: (1) a React Context + localStorage provider for date format preference that wires into `formatDate()` without changing its function signature, and (2) the "Delete All Transactions" flow, which must work around the backend's 100-item batch-delete limit by paginating the delete calls client-side. Everything else is additive UI wiring: a new route, a new nav item, a new settings section, and the removal of the Integrations section.

The main design decision left to Claude (per CONTEXT.md) is the confirmation modal copy and the Notifications section's "Coming Soon" visual treatment. These should follow the existing shadcn/base-ui `AlertDialog` and `SettingSection` patterns already in the codebase.

**Primary recommendation:** Build in this order: (1) Budgets placeholder page + nav item, (2) Date format context + provider + GeneralSection wiring, (3) Delete All Transactions in DataSection, (4) Notifications section + settings nav cleanup. No new dependencies required.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next.js | 16.1.6 | App routing for new `/budgets` route | Already in use |
| React Context API | React 19.2.4 | Date format preference propagation | Built-in; matches `useTheme()` pattern |
| localStorage (browser API) | N/A | Persist date format preference client-side | No backend needed; session-persistent |
| next-themes | ^0.4.6 | Theme toggling (SETT-03) | Already wired; no changes needed |
| sonner | ^2.0.7 | Toast after delete | Already in `layout.tsx` |
| @base-ui/react/alert-dialog | ^1.2.0 | Confirmation modal for delete | Already wrapped in `components/ui/alert-dialog.tsx` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | ^0.575.0 | Icons for Budgets page and Notifications section | Follow established icon usage |
| @tanstack/react-query | ^5.90.21 | Cache invalidation after delete all | `queryClient.invalidateQueries({ queryKey: ['transactions'] })` after bulk delete |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| React Context for date format | Zustand / Jotai | Overkill for a single scalar preference; Context + localStorage is the established pattern (mirrors next-themes) |
| Batch delete loop (client-side pagination) | New backend "delete all" endpoint | Backend is finalized — no server changes; batch loop is clean and safe |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure

New files this phase:

```
src/
├── app/(app)/budgets/
│   └── page.tsx                    # BUDG-01: Coming Soon placeholder
├── providers/
│   └── date-format-provider.tsx    # SETT-02: Context + localStorage
├── hooks/
│   └── use-date-format.ts          # SETT-02: Hook to consume context
└── components/settings/sections/
    └── notifications-section.tsx   # SETT-05: Placeholder toggles
```

Modified files:

```
src/lib/hub-nav.ts                  # Add Budgets nav item
src/lib/format.ts                   # formatDate() reads from context (via hook)
src/app/layout.tsx                  # Wrap with DateFormatProvider
src/components/settings/settings-dialog.tsx   # Add notifications, remove integrations
src/components/settings/sections/general-section.tsx   # Add date format Select
src/components/settings/sections/data-section.tsx      # Add Delete All Transactions
```

### Pattern 1: React Context + localStorage for User Preferences

**What:** Create a context provider that reads initial state from localStorage on mount and writes back on change. Consumers call a hook to get value + setter.

**When to use:** Any user preference that should survive page refresh but requires no backend.

**Example:**

```typescript
// src/providers/date-format-provider.tsx
"use client"

import { createContext, useContext, useState, useEffect, ReactNode } from "react"

export type DateFormat = "de-DE" | "en-US" | "sv-SE"

const DATE_FORMAT_KEY = "pf_date_format"
const DEFAULT_FORMAT: DateFormat = "de-DE"

interface DateFormatContextValue {
  dateFormat: DateFormat
  setDateFormat: (format: DateFormat) => void
}

const DateFormatContext = createContext<DateFormatContextValue>({
  dateFormat: DEFAULT_FORMAT,
  setDateFormat: () => {},
})

export function DateFormatProvider({ children }: { children: ReactNode }) {
  const [dateFormat, setDateFormatState] = useState<DateFormat>(DEFAULT_FORMAT)

  // Read from localStorage after mount (avoids SSR mismatch)
  useEffect(() => {
    const stored = localStorage.getItem(DATE_FORMAT_KEY) as DateFormat | null
    if (stored) setDateFormatState(stored)
  }, [])

  const setDateFormat = (format: DateFormat) => {
    setDateFormatState(format)
    localStorage.setItem(DATE_FORMAT_KEY, format)
  }

  return (
    <DateFormatContext.Provider value={{ dateFormat, setDateFormat }}>
      {children}
    </DateFormatContext.Provider>
  )
}

export function useDateFormat() {
  return useContext(DateFormatContext)
}
```

**Key detail — locale vs. format label:** The context stores a locale string (`"de-DE"`, `"en-US"`, `"sv-SE"`) because `Intl.DateTimeFormat` takes locale, not a format string. The three formats in the requirements map as:
- DD/MM/YYYY (default) → `"de-DE"` → `formatDate(value, "de-DE")` → `"27.02.2026"`
- MM/DD/YYYY (US) → `"en-US"` → `formatDate(value, "en-US")` → `"02/27/2026"`
- YYYY-MM-DD (ISO) → `"sv-SE"` → `formatDate(value, "sv-SE")` → `"2026-02-27"` (Swedish locale uses ISO-style ordering)

**Why sv-SE for ISO:** `Intl.DateTimeFormat` does not accept a raw format string. The ISO `YYYY-MM-DD` ordering is natively produced by the `sv-SE` locale with `{ day: '2-digit', month: '2-digit', year: 'numeric' }` options. This is a well-established workaround — see MDN Intl.DateTimeFormat docs (MEDIUM confidence, consistent with locale output behavior).

### Pattern 2: Wiring formatDate() to Context

**What:** `formatDate()` in `lib/format.ts` already accepts an optional `locale` parameter. Components that call `formatDate()` need to pass the locale from context. Rather than modifying `formatDate()` itself, create a `useFormatDate()` hook that returns a bound version.

**Example:**

```typescript
// src/hooks/use-date-format.ts
"use client"

import { useDateFormat } from "@/providers/date-format-provider"
import { formatDate } from "@/lib/format"

export function useFormatDate() {
  const { dateFormat } = useDateFormat()
  return (value: string) => formatDate(value, dateFormat)
}
```

Components switch from:
```typescript
import { formatDate } from "@/lib/format"
// ...
formatDate(transaction.date)
```

to:
```typescript
const formatDateLocalized = useFormatDate()
// ...
formatDateLocalized(transaction.date)
```

**Alternative considered:** Modifying `formatDate()` to accept context internally. Rejected — `formatDate()` is a pure utility function; injecting a hook call inside it would make it impure and untestable.

### Pattern 3: Delete All Transactions (Pagination Required)

**What:** The backend's `DELETE /transactions/batch` endpoint accepts a maximum of 100 IDs per request. "Delete all" must fetch all transaction IDs first, then delete in batches of 100.

**Critical constraint verified in backend code:** `BatchDeleteRequest.ids` has a max of 100 per the type comment. The `batch_delete` service iterates sequentially — if any ID fails, it rolls back the batch. For "delete all", the approach is:

1. Fetch all transactions (no filters, high limit) to get IDs.
2. Split into chunks of 100.
3. Call `batchDeleteTransactions()` sequentially for each chunk.
4. Invalidate `['transactions']` query cache.
5. Show success toast with count.

```typescript
// src/hooks/use-delete-all-transactions.ts
"use client"

import { useAuth } from "@clerk/nextjs"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { fetchTransactions, batchDeleteTransactions } from "@/lib/api/transactions"

export function useDeleteAllTransactions() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const token = await getToken()
      // Fetch all — use limit:1000 to get IDs in one call for typical datasets
      // Adjust if users could have >1000 transactions (loop until done)
      const allTxns = await fetchTransactions(token, { limit: 1000, offset: 0 })
      const ids = allTxns.items.map((t) => t.id)
      if (ids.length === 0) return 0

      // Batch delete in chunks of 100
      const chunkSize = 100
      let deleted = 0
      for (let i = 0; i < ids.length; i += chunkSize) {
        const chunk = ids.slice(i, i + chunkSize)
        const result = await batchDeleteTransactions(token, { ids: chunk })
        deleted += result.deleted
      }
      return deleted
    },
    onSuccess: (count) => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] })
      queryClient.invalidateQueries({ queryKey: ["analytics"] })
      toast.success(
        count > 0
          ? `${count} transaction${count === 1 ? "" : "s"} deleted`
          : "No transactions to delete"
      )
    },
    onError: () => {
      toast.error("Failed to delete transactions")
    },
  })
}
```

**Note on cache invalidation scope:** After deleting all transactions, the dashboard summary, analytics, and insights data are all stale. Invalidate all three query prefixes (`['transactions']`, `['dashboard']`, `['analytics']`) to prevent stale data showing on other pages.

### Pattern 4: AlertDialog for Confirmation Modal

**What:** The project already uses `@base-ui/react/alert-dialog` wrapped in `components/ui/alert-dialog.tsx`. Use it for the Delete All Transactions confirmation modal.

**Example (inside DataSection):**

```tsx
<AlertDialog>
  <AlertDialogTrigger
    render={
      <Button variant="outline" size="sm" className="border-red-500 text-red-500 hover:text-red-500 hover:bg-red-50">
        Delete All Transactions
      </Button>
    }
  />
  <AlertDialogContent size="sm">
    <AlertDialogHeader>
      <AlertDialogTitle>Delete all transactions?</AlertDialogTitle>
      <AlertDialogDescription>
        This will permanently remove all your transaction history. This action cannot be undone.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction
        variant="destructive"
        onClick={() => deleteAll.mutate()}
        disabled={deleteAll.isPending}
      >
        {deleteAll.isPending ? "Deleting…" : "Delete all"}
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

**Critical:** `AlertDialogTrigger` uses a `render` prop (base-ui pattern), not `asChild` — matches how `DialogTrigger` is used in `settings-dialog.tsx`. `AlertDialogCancel` uses `AlertDialogPrimitive.Close` with a `render` prop. See existing `alert-dialog.tsx` for exact API.

### Pattern 5: Settings Dialog Nav Update

**What:** `settings-dialog.tsx` has a `SettingsSection` union type and `navItems` array. Remove `"integrations"`, add `"notifications"`.

```typescript
// Before:
type SettingsSection = "general" | "integrations" | "data"
const navItems = [
  { id: "general", ... },
  { id: "integrations", ... },   // REMOVE
  { id: "data", ... },
]

// After:
type SettingsSection = "general" | "notifications" | "data"
const navItems = [
  { id: "general", ... },
  { id: "notifications", label: "Notifications", icon: <Bell className="w-5 h-5" /> },
  { id: "data", ... },
]
```

Import `Bell` from `lucide-react`. Import `NotificationsSection`. Remove `IntegrationsSection` import. Delete `integrations-section.tsx` file. Update `renderSection()` switch case.

### Pattern 6: Budgets Placeholder Page

**What:** Add `/budgets` route in the `(app)` group. Server component (no hooks needed). Add `PiggyBank` or `Wallet` icon to `HUB_NAV`.

```tsx
// src/app/(app)/budgets/page.tsx
export default function BudgetsPage() {
  return (
    <main className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center">
      <PiggyBank className="w-16 h-16 text-muted-foreground" />
      <h1 className="text-3xl font-semibold">Coming Soon</h1>
      <p className="text-muted-foreground max-w-sm">
        Budget tracking is on its way. Set spending limits by category, track your progress month by month, and get alerts when you're close to the limit.
      </p>
    </main>
  )
}
```

```typescript
// lib/hub-nav.ts addition
{ title: "Budgets", url: "/budgets", icon: PiggyBank }
```

### Anti-Patterns to Avoid

- **Reading localStorage on the server:** `useEffect` must gate the `localStorage.getItem` call — skip it on server render, hydrate on client. The pattern above handles this correctly.
- **Calling a hook inside a pure utility function:** Do not put `useContext` inside `formatDate()`. Use the `useFormatDate()` hook wrapper instead, and call it inside components.
- **Using `asChild` in base-ui components:** `@base-ui/react` uses `render` prop, not Radix `asChild`. All existing code uses `render={}` — follow the same pattern.
- **Missing cache invalidation breadth:** After "delete all", the dashboard and analytics caches show stale aggregates. Invalidate `['dashboard']` and `['analytics']` in addition to `['transactions']`.
- **Not disabling the confirm button during mutation:** `deleteAll.isPending` must disable the action button to prevent double-clicks during the async delete loop.
- **Hard-coding `limit: 25` for the fetch-all step:** The delete-all flow needs all IDs. Use `limit: 1000` (or the backend's max of 100 per query, repeated) to get them all. The list endpoint accepts up to 100 per page.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Confirmation dialog | Custom modal with useState | `AlertDialog` from `components/ui/alert-dialog.tsx` | Already in the codebase, handles focus trap, a11y, animation |
| Toast notification | Custom toast component | `sonner` via `toast.success()` / `toast.error()` | Already in layout.tsx, styled to match app theme |
| Theme toggle | Custom CSS class switcher | `next-themes` `useTheme()` | Already working — locked decision, do not change |
| LocalStorage reads on SSR | Manual `typeof window` checks | `useEffect` for localStorage access | Prevents hydration mismatch |

**Key insight:** Every primitive needed for this phase is already in the codebase. The phase is additive wiring, not new infrastructure.

---

## Common Pitfalls

### Pitfall 1: localStorage Hydration Mismatch

**What goes wrong:** Reading `localStorage` during SSR renders a different value than the client, causing React hydration error.

**Why it happens:** Next.js SSR runs components on the server where `localStorage` is undefined. If you read it in component body or `useState` initializer, the server and client render different HTML.

**How to avoid:** Always read `localStorage` inside `useEffect(() => { ... }, [])`. Initialize state with the default value (`"de-DE"`), then update after mount.

**Warning signs:** React hydration error in console: "Hydration failed because the server-rendered HTML didn't match the client."

### Pitfall 2: AlertDialogTrigger render prop vs children

**What goes wrong:** Using `<AlertDialogTrigger>` with children instead of the `render` prop causes a TypeScript error or runtime failure.

**Why it happens:** `@base-ui/react` uses `render` prop pattern, not Radix's `asChild`. Looking at `alert-dialog.tsx` line 13–16, `AlertDialogTrigger` passes directly to `AlertDialogPrimitive.Trigger` which accepts `render`.

**How to avoid:** Model exactly how `DialogTrigger` is used in `settings-dialog.tsx` line 56–63: `render={<Button ...>}`.

**Warning signs:** TypeScript error "Property 'asChild' does not exist" or trigger element renders but onClick does nothing.

### Pitfall 3: Batch Delete Limit (100 items max)

**What goes wrong:** Passing more than 100 IDs to `batchDeleteTransactions()` — the backend type comment says "Maximum 100 ids per request". If passed more, the request may be rejected or silently truncated.

**Why it happens:** `BatchDeleteRequest` schema in the backend likely has a Pydantic `max_length` or `max_items` validator on the list field.

**How to avoid:** Always chunk IDs into groups of 100 before calling `batchDeleteTransactions()`. See Pattern 3 code above.

**Warning signs:** 422 Validation Error from backend when deleting users with >100 transactions.

### Pitfall 4: formatDate Called in Server Components

**What goes wrong:** `useFormatDate()` is a hook and cannot be called in Server Components (RSC). If `formatDate` is called in a server page or layout, it won't have access to the context.

**Why it happens:** Context is client-only. Server components don't run client hooks.

**How to avoid:** Check which components currently call `formatDate()`. If any are Server Components, they must either be converted to `"use client"` or continue using the default locale. The transactions table, dashboard recent transactions, etc., are already Client Components (they use hooks) — no issue there.

**Warning signs:** "You're importing a component that needs useState/useContext" build error.

### Pitfall 5: Settings Dialog Has Nested Sidebar — Collapsible="none" Required

**What goes wrong:** The inner `Sidebar` in `settings-dialog.tsx` uses `collapsible="none"`. If someone tries to use the responsive sidebar behavior inside the modal, it will conflict with the outer app sidebar state.

**Why it happens:** `SidebarProvider` from the app layout wraps everything including the dialog content. The inner sidebar must be static.

**How to avoid:** Keep `collapsible="none"` on the settings sidebar (already set). Do not add `SidebarProvider` inside the dialog.

---

## Code Examples

Verified patterns from codebase inspection:

### Existing AlertDialog usage pattern (from alert-dialog.tsx)

```tsx
// AlertDialogTrigger uses render prop (base-ui pattern)
<AlertDialogTrigger render={<Button>Open</Button>} />

// AlertDialogCancel uses render prop via Close primitive
<AlertDialogCancel variant="outline">Cancel</AlertDialogCancel>

// AlertDialogAction is just a Button wrapper
<AlertDialogAction variant="destructive">Confirm</AlertDialogAction>
```

### Existing toast usage pattern (from use-transaction-mutations.ts)

```typescript
import { toast } from "sonner"
// In onSuccess:
toast.success("Category updated")
// In onError:
toast.error("Failed to update category")
```

### Existing SettingSection pattern (from general-section.tsx)

```tsx
<SettingSection title="Aspect">
  <div className="flex items-center justify-between">
    <Label>Theme</Label>
    <Select value={theme} onValueChange={(value) => { if (value) setTheme(value) }}>
      <SelectTrigger className="w-34">
        <SelectValue>...</SelectValue>
      </SelectTrigger>
      <SelectContent>...</SelectContent>
    </Select>
  </div>
</SettingSection>
```

### Date format Select (SETT-02 implementation sketch)

```tsx
// In GeneralSection, below existing "Aspect" SettingSection
const FORMAT_OPTIONS = [
  { value: "de-DE", label: "DD/MM/YYYY", example: "27.02.2026" },
  { value: "en-US", label: "MM/DD/YYYY", example: "02/27/2026" },
  { value: "sv-SE", label: "YYYY-MM-DD", example: "2026-02-27" },
]

<SettingSection title="Regional">
  <div className="flex items-center justify-between">
    <Label>Date Format</Label>
    <Select value={dateFormat} onValueChange={(value) => { if (value) setDateFormat(value as DateFormat) }}>
      <SelectTrigger className="w-34">
        <SelectValue>
          {FORMAT_OPTIONS.find(o => o.value === dateFormat)?.label}
        </SelectValue>
      </SelectTrigger>
      <SelectContent className="min-w-40 max-w-40">
        {FORMAT_OPTIONS.map(opt => (
          <SelectItem key={opt.value} value={opt.value}>
            <span>{opt.label}</span>
            <span className="text-muted-foreground text-xs ml-2">{opt.example}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  </div>
</SettingSection>
```

### Notifications section placeholder pattern (SETT-05)

```tsx
// notifications-section.tsx — follows SettingSection + Label pattern
"use client"
import { SettingSection } from "@/components/ui/setting-section"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"

export function NotificationsSection() {
  return (
    <div className="space-y-6">
      <SettingSection title="Preferences">
        <div className="flex items-center justify-between">
          <div>
            <Label>Email Alerts</Label>
            <p className="text-xs text-muted-foreground">Receive email summaries</p>
          </div>
          <Badge variant="secondary">Coming Soon</Badge>
        </div>
        {/* budget alerts, newsletter — same pattern */}
      </SettingSection>
    </div>
  )
}
```

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| Radix UI `asChild` for polymorphic triggers | `@base-ui/react` `render` prop | This project uses base-ui, not Radix — all dialog primitives use `render={}` |
| `next-themes` HTML attribute approach | `attribute="class"` (already set) | ThemeProvider in layout.tsx already configured correctly |
| Per-component localStorage reads | Context + Provider pattern | Provider reads once, distributes via context — avoids scattered localStorage calls |

---

## Open Questions

1. **Fetch limit for "delete all" IDs**
   - What we know: `fetchTransactions` accepts `limit` up to 100 per the backend query param validation (`le=100`). The `list_transactions` route has `limit: int = Query(20, ge=1, le=100)`.
   - What's unclear: If a user has >100 transactions, a single fetch won't return all IDs.
   - Recommendation: Paginate the fetch step — loop with `offset` until `items.length < limit`, collecting all IDs before deleting. The delete hook must handle this loop. This adds complexity but is correct.

2. **sv-SE locale for ISO date format**
   - What we know: `Intl.DateTimeFormat("sv-SE", { day: "2-digit", month: "2-digit", year: "numeric" })` produces `"2026-02-27"` in modern browsers.
   - What's unclear: Behavior in older browsers or edge environments.
   - Recommendation: Use sv-SE. If concerned, add a simple format helper that manually constructs the YYYY-MM-DD string for the ISO case instead of relying on locale.

3. **Query invalidation scope after delete all**
   - What we know: `['transactions']`, `['dashboard']`, `['analytics']` queries all derive from transaction data.
   - What's unclear: Whether insights cache also needs invalidation (insights are cached separately under `['insights']`).
   - Recommendation: Invalidate insights too — after deleting all transactions, cached insights are completely stale and would show misleading data.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `components/settings/settings-dialog.tsx`, `general-section.tsx`, `data-section.tsx`, `integrations-section.tsx` — confirmed exact file structure and patterns
- Direct codebase inspection: `components/ui/alert-dialog.tsx` — confirmed base-ui `render` prop pattern, available components
- Direct codebase inspection: `lib/format.ts` — confirmed `formatDate()` signature accepts optional `locale` param
- Direct codebase inspection: `lib/api/transactions.ts`, `hooks/use-transaction-mutations.ts` — confirmed `batchDeleteTransactions()` API shape
- Direct codebase inspection: `server/app/api/v1/transactions.py`, `server/app/services/transaction/service.py` — confirmed no "delete all" endpoint exists; batch limit context
- Direct codebase inspection: `types/transaction.ts` — confirmed `BatchDeleteRequest` comment "Maximum 100 ids per request"
- Direct codebase inspection: `lib/hub-nav.ts`, `types/nav.ts` — confirmed nav item structure for Budgets addition
- Direct codebase inspection: `app/layout.tsx`, `components/ui/theme-provider.tsx`, `providers/query-provider.tsx` — confirmed provider nesting, where to inject DateFormatProvider
- Direct codebase inspection: `package.json` — confirmed all required libraries present, no new installs needed

### Secondary (MEDIUM confidence)
- `Intl.DateTimeFormat` sv-SE locale for ISO date output — well-known pattern; not verified against MDN in this session but consistent with established practice

### Tertiary (LOW confidence)
- Backend max batch size of 100 inferred from TypeScript type comment — not verified against actual Pydantic schema validation in server/app/schemas/transaction.py

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries directly verified in package.json and existing files
- Architecture: HIGH — all patterns traced directly from existing code in the same codebase
- Pitfalls: HIGH (items 1–5) — derived from direct code inspection of base-ui usage, Next.js SSR constraints, and backend API shape
- sv-SE locale mapping: MEDIUM — established practice, not freshly verified

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (stable stack — 30 days)

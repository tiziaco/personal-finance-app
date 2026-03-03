# Phase 5: Insights - Research

**Researched:** 2026-03-02
**Domain:** AI insights UI — React Query refetch pattern, client-side cooldown, insight card layout, savings tracker
**Confidence:** HIGH

## Summary

Phase 5 builds the dedicated Insights page at `/insights`. The core challenge is not AI integration (the backend handles all generation) but rather the UX contract around the "Generate New Insights" button: the backend has **only a single `GET /api/v1/insights` endpoint** — there is no POST trigger. Generation happens automatically server-side on first call and whenever transactions are newer than the cached result. The frontend must simulate a "generate" experience by calling `refetch()` on the React Query `useInsights` hook and enforcing a 1-hour client-side cooldown via `localStorage`.

The second major challenge is mapping backend insight data to the UI card format. The `Insight` type from the backend includes a `section` field (`"spending"`, `"subscriptions"`, `"trends"`, `"anomalies"`, `"behavior"`) that maps to the five UI categories. Crucially, there is no `action_cta` field in the backend schema — any CTA must be derived on the frontend from `insight.type` or `insight.section`. The `supporting_metrics` field is `Record<string, unknown>`, so all key metric extraction must use defensive access with fallback values.

The savings tracker (INSGT-06) must aggregate `monthly_cost` from `supporting_metrics` of subscription-type insights (section `"subscriptions"`, type `"recurring_subscriptions"`). The checklist state (which recommendations are "done") is purely client-side — there is no backend persistence for this in v1.

**Primary recommendation:** Build the Insights page at `/insights` as a new route with a single `InsightsPage` component. Implement the generate button with React Query `refetch()` + `localStorage` cooldown timestamp. Map `insight.section` to display categories. Derive key metrics from `supporting_metrics` with defensive access. Store savings tracker checkboxes in `useState` only (no persistence in v1).

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INSGT-01 | Prominent "Generate New Insights" button at top of Insights page | React Query `refetch()` on `useInsights`, `localStorage` for cooldown persistence; button calls `refetch()` and sets cooldown timestamp |
| INSGT-02 | Loading spinner and disabled button state during generation | React Query `isFetching` state drives disabled + spinner; `useInsights` already has `staleTime: 10min` which must be overridden when user manually triggers |
| INSGT-03 | Generate button disabled with countdown ("Refreshes in XX minutes") for 1 hour after generation | Client-side cooldown: store `generated_at` timestamp in `localStorage`; compute remaining minutes with `setInterval`; no backend enforcement |
| INSGT-04 | Insight cards organized by category (Spending Patterns, Recurring Charges, Savings Opportunities, Anomalies, Comparisons) as tabs or accordion | Map `insight.section` → display category; use Base UI `Tabs` (same as analytics page) or shadcn `Accordion`; sections with zero insights show empty sub-state |
| INSGT-05 | Each insight card shows: title, icon, description (2-3 sentences), key metric, optional CTA, timestamp | `summary` → title/description; `supporting_metrics` (defensive access) → key metric; icon derived from `type`; CTA derived from `section`; `generated_at` from response envelope |
| INSGT-06 | Savings tracker showing total potential monthly savings + checklist to mark recommendations as done | Aggregate `supporting_metrics.monthly_cost` from `section: "subscriptions"` insights; checkbox state in `useState`; total recomputed from unchecked items |
| INSGT-07 | Empty state with illustration and "Generate Insights" CTA when no insights generated yet | `insights.length === 0 && !isFetching` condition; reuse illustration pattern from transactions empty state |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @tanstack/react-query | ^5.90.21 | Server state, refetch, isFetching | Already installed; `useInsights` hook exists and is wired to `GET /api/v1/insights` |
| lucide-react | ^0.575.0 | Icons for insight type/section | Already installed throughout the app |
| @base-ui/react | ^1.2.0 | Tabs component for category navigation | Already used in analytics page (`/stats`); consistent UX |
| sonner | ^2.0.7 | Toast notification on generate success/error | Already installed; used in error boundaries |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn Accordion | via shadcn | Alternative to tabs for insight categories | Only if tabs feel visually heavy; tabs are preferred (consistent with analytics) |
| next-themes | ^0.4.6 | Dark mode | Already in use; no new work needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Base UI Tabs | shadcn Tabs | Base UI already used in analytics — use Base UI for consistency |
| localStorage cooldown | React state only | localStorage survives page refresh; state-only resets cooldown on navigation — use localStorage |
| localStorage cooldown | Backend enforcement | No POST endpoint exists; backend cooldown not available in v1 |

**No new packages needed.** All required libraries are already in `package.json`.

---

## Architecture Patterns

### Recommended Project Structure
```
src/
├── app/(app)/insights/        # New route
│   └── page.tsx               # InsightsPage — 'use client'
├── components/insights/       # New component directory
│   ├── generate-button.tsx    # Generate button with cooldown state
│   ├── insight-card.tsx       # Single insight card
│   ├── insight-category-tabs.tsx  # Tabbed category view
│   └── savings-tracker.tsx    # Savings tracker with checklist
├── hooks/
│   └── use-insights.ts        # Already exists — may need useGenerateInsights wrapper
└── lib/
    └── insights-helpers.ts    # Section → category mapping, icon map, metric extraction
```

### Pattern 1: Generate Button with React Query Refetch + localStorage Cooldown

**What:** The generate button calls React Query's `refetch()` (not a new mutation) and stores a cooldown timestamp in localStorage. A `setInterval` ticks down the remaining minutes for display.

**When to use:** When the only available API is a GET that handles generation server-side.

**Critical constraint:** `useInsights` has `staleTime: 10 * 60 * 1000` (10 min). Calling `refetch()` bypasses staleTime and forces a fresh fetch regardless of cache. This is the correct approach.

**Example:**
```typescript
// Source: @tanstack/react-query v5 docs — refetch bypasses staleTime
import { useInsights } from '@/hooks/use-insights'

const COOLDOWN_KEY = 'insights_last_generated'
const COOLDOWN_MS = 60 * 60 * 1000  // 1 hour

function useInsightsGenerate() {
  const { refetch, isFetching } = useInsights()
  const [cooldownRemaining, setCooldownRemaining] = useState<number>(0)

  // Hydrate cooldown from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(COOLDOWN_KEY)
    if (stored) {
      const elapsed = Date.now() - parseInt(stored, 10)
      const remaining = Math.max(0, COOLDOWN_MS - elapsed)
      setCooldownRemaining(remaining)
    }
  }, [])

  // Tick down the countdown every 30 seconds
  useEffect(() => {
    if (cooldownRemaining <= 0) return
    const id = setInterval(() => {
      setCooldownRemaining(prev => Math.max(0, prev - 30_000))
    }, 30_000)
    return () => clearInterval(id)
  }, [cooldownRemaining])

  const generate = async () => {
    await refetch()
    const now = Date.now()
    localStorage.setItem(COOLDOWN_KEY, String(now))
    setCooldownRemaining(COOLDOWN_MS)
  }

  const minutesRemaining = Math.ceil(cooldownRemaining / 60_000)
  const isOnCooldown = cooldownRemaining > 0
  const isDisabled = isFetching || isOnCooldown

  return { generate, isDisabled, isFetching, isOnCooldown, minutesRemaining }
}
```

### Pattern 2: Section → Category Mapping

**What:** Map backend `insight.section` values to display category names and icons.

**Backend sections observed in aggregator.py:**
- `"spending"` → Spending Patterns
- `"subscriptions"` → Recurring Charges
- `"trends"` → Comparisons (trends + stability)
- `"anomalies"` → Anomalies (merchant concentration + outliers)
- `"behavior"` → Spending Patterns (behavioral insights)

**Note:** The UI requirement lists 5 categories: Spending Patterns, Recurring Charges, Savings Opportunities, Anomalies, Comparisons. Backend has no "savings" section — Savings Opportunities must be derived from `type: "recurring_subscriptions"` insights (they have `monthly_cost` in `supporting_metrics`).

**Example:**
```typescript
// Source: server/app/agents/insights/aggregator.py — actual section values
import { TrendingUp, RefreshCw, PiggyBank, AlertTriangle, BarChart2 } from 'lucide-react'

const SECTION_CONFIG = {
  spending_patterns: {
    label: 'Spending Patterns',
    icon: TrendingUp,
    sections: ['spending', 'behavior'],  // backend section values
  },
  recurring_charges: {
    label: 'Recurring Charges',
    icon: RefreshCw,
    sections: ['subscriptions'],
  },
  savings_opportunities: {
    label: 'Savings Opportunities',
    icon: PiggyBank,
    // derived: insights where supporting_metrics.monthly_cost exists
    sections: ['subscriptions'],
    filter: (insight: Insight) => !!insight.supporting_metrics?.monthly_cost,
  },
  anomalies: {
    label: 'Anomalies',
    icon: AlertTriangle,
    sections: ['anomalies'],
  },
  comparisons: {
    label: 'Comparisons',
    icon: BarChart2,
    sections: ['trends'],
  },
} as const
```

### Pattern 3: Defensive Key Metric Extraction

**What:** `supporting_metrics` is `Record<string, unknown>` — extract display values safely.

**Example:**
```typescript
// Source: server/app/schemas/insights.py — supporting_metrics: Dict[str, Any]
function getKeyMetric(insight: Insight): string | null {
  const m = insight.supporting_metrics

  if (insight.type === 'recurring_subscriptions') {
    const cost = m?.monthly_cost
    if (typeof cost === 'number') return formatCurrency(cost) + '/month'
  }
  if (insight.type === 'spending_behavior') {
    const pct = m?.percentage
    if (typeof pct === 'number') return formatPercent(pct)
  }
  if (insight.type === 'anomaly') {
    const count = m?.anomaly_count
    if (typeof count === 'number') return `${count} outliers detected`
  }
  // Fallback: show confidence score
  return `${Math.round(insight.confidence * 100)}% confidence`
}
```

### Pattern 4: Savings Tracker

**What:** Aggregate `monthly_cost` from subscription insights; checkbox state is `useState` only (no backend persistence in v1).

**Example:**
```typescript
// No backend endpoint for savings tracking — client state only
const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())

const savingsInsights = insights.filter(
  i => i.type === 'recurring_subscriptions' &&
       typeof i.supporting_metrics?.monthly_cost === 'number'
)

const totalSavings = savingsInsights
  .filter(i => !checkedIds.has(i.insight_id))
  .reduce((sum, i) => sum + (i.supporting_metrics.monthly_cost as number), 0)
```

### Pattern 5: New `/insights` Route

**What:** The Insights page needs a new route. Currently the navigation uses `/stats` for Analytics. A new `/insights` route must be added and registered in `HUB_NAV`.

**Critical:** The existing `insights-callout.tsx` on the dashboard links to `/stats` as the placeholder for "View Insights" and "Generate New Insights". After this phase, those links must point to `/insights`.

**Navigation update needed in:** `src/lib/hub-nav.ts` — add Insights entry with `Lightbulb` or `Sparkles` icon.

### Anti-Patterns to Avoid

- **Calling `refetch()` inside `onMount` or `useEffect`:** This bypasses the staleTime naturally — only call `refetch()` when user clicks the button. Do NOT add `enabled: false` to `useInsights` and manually trigger; the hook must continue to auto-fetch on page load.
- **Using `invalidateQueries` for the generate flow:** `invalidateQueries` marks stale but does not immediately refetch. Use `refetch()` for the generate button to get immediate feedback.
- **Persisting savings tracker to localStorage:** Out of scope for v1. `useState` only. Adding persistence creates debt without backend sync.
- **Building separate `useMutation` for generation:** There is no POST endpoint. Do not add one. The GET endpoint handles everything.
- **Assuming `insights.length === 0` means "never generated":** An empty insights array could mean generation ran but found nothing. Check `insightsData` being `undefined` vs `insightsData.insights.length === 0` separately for the empty state message.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Countdown display | Custom date-diff math component | `Math.ceil(cooldownRemaining / 60_000)` inline | Simple arithmetic; no library needed |
| Tabs UI for categories | Custom tab component | Base UI `Tabs` (already used in `/stats`) | Consistent with existing analytics page |
| Icon selection | Custom icon registry system | Simple `Record<InsightType, LucideIcon>` const | lucide-react already installed |
| Toast on generate success/error | Custom notification | `sonner` toast (already used) | Already the project standard |
| Insight skeleton loading | New skeleton component | `InsightCardSkeleton` already exists at `components/shared/skeletons/insight-card-skeleton.tsx` | Already built in Phase 1 |

**Key insight:** The `InsightCardSkeleton` component was built in Phase 1 specifically for this phase. Use it for the loading state of the full insights list.

---

## Common Pitfalls

### Pitfall 1: staleTime Blocks Manual Refetch
**What goes wrong:** Developer calls `refetch()` but `useInsights` has `staleTime: 10min`. In React Query v5, `refetch()` **does bypass staleTime** by default — data will actually be fetched. However, the developer must NOT wrap the generate call with `queryClient.setQueryData` or it will interfere.
**Why it happens:** Confusion between `invalidateQueries` (respects staleTime) vs `refetch()` (always fetches).
**How to avoid:** Call `refetch()` directly from the hook. Do not call `invalidateQueries` before `refetch()`.
**Warning signs:** Button clicks appear to load but data doesn't update; `isFetching` stays false.

### Pitfall 2: Cooldown State Lost on Page Refresh Without localStorage
**What goes wrong:** User generates insights, navigates away, comes back — cooldown is reset. Button is clickable immediately.
**Why it happens:** Cooldown stored only in `useState` doesn't survive navigation/refresh.
**How to avoid:** Store timestamp in `localStorage` under a stable key (e.g., `insights_last_generated`). Hydrate on mount. Note: localStorage is not available during SSR — wrap access in `useEffect` or guard with `typeof window !== 'undefined'`.
**Warning signs:** Countdown resets to 0 every page load.

### Pitfall 3: `generated_at` is the Response Envelope Timestamp, Not Per-Card
**What goes wrong:** Developer tries to show "Generated at [time]" per insight card using a field that doesn't exist. The `Insight` type has no `generated_at` — only the `InsightsResponse` envelope does.
**Why it happens:** Misreading the schema.
**How to avoid:** Pass `insightsData.generated_at` down to the card as a prop. All cards in a batch share the same timestamp.
**Warning signs:** TypeScript error accessing `insight.generated_at`.

### Pitfall 4: "Savings Opportunities" Category Has No Direct Backend Section
**What goes wrong:** Developer filters insights by `section === 'savings'` and gets zero results, showing empty state for that tab.
**Why it happens:** Backend sections are `spending`, `subscriptions`, `trends`, `anomalies`, `behavior`. There is no `savings` section.
**How to avoid:** Derive "Savings Opportunities" from insights where `type === 'recurring_subscriptions'` AND `supporting_metrics.monthly_cost` is a number. These are the same insights shown in "Recurring Charges" — Savings Opportunities is a filtered sub-view.
**Warning signs:** Savings Opportunities tab always shows empty state even when subscription insights exist.

### Pitfall 5: Navigation Not Updated
**What goes wrong:** Insights page exists at `/insights` but is unreachable from the sidebar. The dashboard callout still points to `/stats`.
**Why it happens:** `hub-nav.ts` and `insights-callout.tsx` links not updated.
**How to avoid:** As part of this phase, update `hub-nav.ts` to add `/insights` and update `insights-callout.tsx` links from `/stats` to `/insights`.
**Warning signs:** User can't find Insights page from sidebar.

### Pitfall 6: Accessing `supporting_metrics` Values Without Type Guards
**What goes wrong:** `supporting_metrics.monthly_cost` throws at runtime because TypeScript types it as `unknown`.
**Why it happens:** `supporting_metrics: Record<string, unknown>` — all values are `unknown`.
**How to avoid:** Always guard: `typeof insight.supporting_metrics?.monthly_cost === 'number'` before using. Never cast directly.
**Warning signs:** TypeScript errors `Type 'unknown' is not assignable to type 'number'`.

---

## Code Examples

### Using `refetch()` with loading state (React Query v5)
```typescript
// Source: @tanstack/react-query v5 — refetch always bypasses staleTime
const { data, refetch, isFetching } = useInsights()

const handleGenerate = async () => {
  try {
    await refetch()
    toast.success('Insights updated')
  } catch {
    toast.error('Failed to generate insights')
  }
}
```

### Base UI Tabs pattern (from existing analytics page)
```typescript
// Source: web-app/src/app/(app)/stats/page.tsx — exact pattern used in Phase 4
import { Tabs } from '@base-ui/react/tabs'

<Tabs.Root value={activeCategory} onValueChange={handleCategoryChange}>
  <Tabs.List className="flex border-b border-border">
    {INSIGHT_CATEGORIES.map(cat => (
      <Tabs.Tab
        key={cat.value}
        value={cat.value}
        className={cn(
          'px-4 py-2 text-sm font-medium text-muted-foreground',
          'data-[active]:text-foreground data-[active]:border-b-2 data-[active]:border-primary',
          'focus-visible:outline-none transition-colors cursor-pointer'
        )}
      >
        {cat.label}
      </Tabs.Tab>
    ))}
  </Tabs.List>
  {/* Tab panels */}
</Tabs.Root>
```

### Countdown display
```typescript
// Simple inline — no library needed
const minutesRemaining = Math.ceil(cooldownRemaining / 60_000)

<Button disabled={isDisabled}>
  {isFetching
    ? 'Generating...'
    : isOnCooldown
    ? `Refreshes in ${minutesRemaining} minute${minutesRemaining === 1 ? '' : 's'}`
    : 'Generate New Insights'
  }
</Button>
```

### localStorage hydration (SSR-safe)
```typescript
// Source: standard Next.js SSR-safe localStorage pattern
useEffect(() => {
  if (typeof window === 'undefined') return
  const stored = localStorage.getItem(COOLDOWN_KEY)
  if (!stored) return
  const elapsed = Date.now() - parseInt(stored, 10)
  const remaining = Math.max(0, COOLDOWN_MS - elapsed)
  setCooldownRemaining(remaining)
}, [])
```

### Insight card timestamp display
```typescript
// generated_at is on InsightsResponse envelope, not on individual Insight
// Pass it down as a prop
interface InsightCardProps {
  insight: Insight
  generatedAt: string  // ISO 8601 from InsightsResponse.generated_at
}

// Display:
<span className="text-xs text-muted-foreground">
  Generated {formatDate(generatedAt)}
</span>
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `invalidateQueries` for manual refresh | `refetch()` for immediate forced fetch | React Query v5 | `refetch()` bypasses staleTime; `invalidateQueries` does not trigger immediate fetch |
| Separate POST endpoint for AI generation | Single GET with server-side auto-generation | This project's backend design | Frontend must treat GET as the trigger; no mutation hook needed |

---

## Open Questions

1. **Does the backend enforce its own rate limiting on `GET /api/v1/insights`?**
   - What we know: `@limiter.limit("10/minute")` is applied to the GET endpoint (confirmed in `server/app/api/v1/insights.py` line 24)
   - What's unclear: Whether 10/minute is enough headroom or if the 1-hour frontend cooldown is sufficient protection
   - Recommendation: The 1-hour frontend cooldown far exceeds the 10/minute rate limit — no conflict expected. Document the rate limit for debugging if users hit 429 errors.

2. **Should the Insights page replace or coexist with `/stats`?**
   - What we know: `/stats` is the Analytics page. The "View Insights" and "Generate New Insights" CTAs in `insights-callout.tsx` currently link to `/stats` as a placeholder.
   - What's unclear: Whether Phase 5 should rename `/stats` to `/analytics` or create `/insights` as a separate route.
   - Recommendation: Create a new `/insights` route. Leave `/stats` as Analytics. Update `insights-callout.tsx` links to `/insights`. Add `/insights` to `hub-nav.ts`.

3. **What icon to use for insight types vs categories?**
   - What we know: `lucide-react` is available with hundreds of icons.
   - What's unclear: Exact icon choices aren't specified in requirements.
   - Recommendation: Use `Sparkles` for Spending Patterns, `RefreshCw` for Recurring Charges, `PiggyBank` for Savings Opportunities, `AlertTriangle` for Anomalies, `BarChart2` for Comparisons. These are all available in lucide-react ^0.575.0.

---

## Backend API Reference (Confirmed)

**Endpoint:** `GET /api/v1/insights`
**Auth:** Bearer token (Clerk JWT)
**Rate limit:** 10/minute (confirmed in source)
**Behavior:**
- First call with no cached row: generates synchronously (may take 30+ seconds)
- Subsequent calls: returns cached row immediately
- Auto-regenerates if any transaction has `created_at > insight.generated_at`
- No POST, no separate trigger endpoint

**Response shape** (from `server/app/schemas/insights.py`):
```typescript
{
  insights: Array<{
    insight_id: string          // e.g. "top_spending_category"
    type: InsightType           // "spending_behavior" | "recurring_subscriptions" | "trend" | "behavioral" | "merchant" | "stability" | "anomaly"
    severity: SeverityLevel     // "info" | "low" | "medium" | "high" | "critical"
    time_window: string         // e.g. "last_period", "monthly", "last_3_months"
    summary: string             // 1-2 sentence human-readable summary
    narrative_analysis: string | null   // longer LLM-generated analysis (may be null)
    supporting_metrics: Record<string, unknown>   // varies by type
    confidence: number          // 0.0 – 1.0
    section: string             // "spending" | "subscriptions" | "trends" | "anomalies" | "behavior"
  }>
  generated_at: string          // ISO 8601 datetime
}
```

**Supporting metrics shapes by type** (confirmed from aggregator.py):
- `spending_behavior`: `{ category, percentage, amount }`
- `recurring_subscriptions`: `{ percentage, monthly_cost, recurring_count }`
- `trend`: `{ mom_growth }`
- `behavioral`: `{ weekend_bias_percentage }`
- `merchant`: `{ top_5_merchants_pct, concentration_risk, ... }`
- `stability`: `{ stable_percentage, volatile_percentage, ... }`
- `anomaly`: `{ anomaly_count, top_outlier: { merchant, amount_abs, z_score } }`

---

## Sources

### Primary (HIGH confidence)
- `server/app/api/v1/insights.py` — confirmed GET-only endpoint, rate limit decorator
- `server/app/services/insights/service.py` — confirmed auto-generation logic, staleness check
- `server/app/schemas/insights.py` — confirmed Insight schema with all fields
- `server/app/agents/insights/aggregator.py` — confirmed `section` values and `supporting_metrics` shapes per type
- `web-app/src/hooks/use-insights.ts` — confirmed existing hook with `staleTime: 10min`
- `web-app/src/types/insights.ts` — confirmed frontend type definitions
- `web-app/src/components/dashboard/insights-callout.tsx` — confirmed current placeholder links to `/stats`
- `web-app/src/app/(app)/stats/page.tsx` — confirmed Base UI Tabs pattern to reuse
- `web-app/package.json` — confirmed all dependencies (no new packages needed)

### Secondary (MEDIUM confidence)
- React Query v5 docs (from training knowledge, verified against installed version ^5.90.21): `refetch()` bypasses staleTime, returns a Promise

### Tertiary (LOW confidence)
- None — all critical findings backed by source code inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in package.json, no new dependencies needed
- Architecture: HIGH — backend schema fully confirmed from source; frontend patterns derived from existing pages
- Pitfalls: HIGH — most pitfalls identified from direct source inspection (schema gaps, missing sections, localStorage SSR)

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (backend is finalized per REQUIREMENTS.md — "Modifying /server backend: Backend finalized — frontend consumes only")

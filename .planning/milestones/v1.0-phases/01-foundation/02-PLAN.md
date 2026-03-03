---
phase: 01-foundation
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - web-app/src/components/shared/skeletons/card-skeleton.tsx
  - web-app/src/components/shared/skeletons/table-skeleton.tsx
  - web-app/src/components/shared/skeletons/chart-skeleton.tsx
  - web-app/src/components/shared/skeletons/insight-card-skeleton.tsx
  - web-app/src/components/shared/error-boundary.tsx
autonomous: true
requirements:
  - FOUND-05
  - FOUND-06

must_haves:
  truths:
    - "Four skeleton variants exist covering all data-bearing UI regions (cards, table rows, charts, insight cards)"
    - "All skeleton components use the shadcn Skeleton primitive (animate-pulse, no custom CSS)"
    - "An ErrorBoundary class component exists that catches render errors and shows a fallback UI"
    - "ErrorBoundary does NOT use React hooks (class component constraint)"
    - "ErrorBoundary accepts an optional fallback prop for custom error UIs"
  artifacts:
    - path: "web-app/src/components/shared/skeletons/card-skeleton.tsx"
      provides: "Skeleton for summary cards (count prop for 1-4 cards)"
      exports: ["CardSkeleton"]
    - path: "web-app/src/components/shared/skeletons/table-skeleton.tsx"
      provides: "Skeleton for transaction table (rows prop)"
      exports: ["TableSkeleton"]
    - path: "web-app/src/components/shared/skeletons/chart-skeleton.tsx"
      provides: "Skeleton for chart loading region"
      exports: ["ChartSkeleton"]
    - path: "web-app/src/components/shared/skeletons/insight-card-skeleton.tsx"
      provides: "Skeleton for insight cards (count prop)"
      exports: ["InsightCardSkeleton"]
    - path: "web-app/src/components/shared/error-boundary.tsx"
      provides: "ErrorBoundary class component"
      exports: ["ErrorBoundary"]
  key_links:
    - from: "web-app/src/components/shared/skeletons/card-skeleton.tsx"
      to: "@/components/ui/skeleton"
      via: "direct import"
      pattern: "import.*Skeleton.*from.*@/components/ui/skeleton"
    - from: "web-app/src/components/shared/error-boundary.tsx"
      to: "react"
      via: "Component class import"
      pattern: "import.*Component.*from.*react"
---

<objective>
Create all shared skeleton loading components and the ErrorBoundary class component. These primitives are independent of types, API functions, and hooks — they can be built in parallel with the type layer (Plan 01).

Purpose: Every data-bearing region of the app needs a loading state and an error recovery path. Creating these upfront means downstream page plans can immediately apply them without coming back to the foundation layer.

Output: Four skeleton variants + ErrorBoundary class component in web-app/src/components/shared/.
</objective>

<execution_context>
@/Users/tizianoiacovelli/.claude/get-shit-done/workflows/execute-plan.md
@/Users/tizianoiacovelli/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Key constraints:
- shadcn `Skeleton` primitive is already installed at `@/components/ui/skeleton` — use it directly, never animate manually
- shadcn `Card`, `CardContent`, `CardHeader` are installed — CardSkeleton should use them to match actual card dimensions
- ErrorBoundary MUST be a class component (React constraint — error boundaries cannot be function components)
- Do NOT install react-error-boundary package — STATE.md flags this as an open question. Default to the custom class implementation (zero new dependency). If the package is already present in package.json, you may use it, but check first.
- ErrorBoundary must NOT use hooks inside the class (no useState, useQueryClient, etc. — class component cannot use hooks)
- Toast on error: use `import { toast } from 'sonner'` (regular function, not a hook) inside `componentDidCatch` to fire a toast notification
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create skeleton components</name>
  <files>
    web-app/src/components/shared/skeletons/card-skeleton.tsx,
    web-app/src/components/shared/skeletons/table-skeleton.tsx,
    web-app/src/components/shared/skeletons/chart-skeleton.tsx,
    web-app/src/components/shared/skeletons/insight-card-skeleton.tsx
  </files>
  <action>
Create the directory `web-app/src/components/shared/skeletons/` and the four files below.

**File 1: card-skeleton.tsx**
```tsx
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

interface CardSkeletonProps {
  count?: number  // default 1; use 4 for the dashboard summary cards row
}

export function CardSkeleton({ count = 1 }: CardSkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <Skeleton className="h-4 w-32" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-8 w-24 mb-2" />
            <Skeleton className="h-3 w-16" />
          </CardContent>
        </Card>
      ))}
    </>
  )
}
```

**File 2: table-skeleton.tsx**
```tsx
import { Skeleton } from '@/components/ui/skeleton'

interface TableSkeletonProps {
  rows?: number     // default 10; use 25 for full transaction table page
  columns?: number  // default 7; matches transaction table column count
}

export function TableSkeleton({ rows = 10, columns = 7 }: TableSkeletonProps) {
  return (
    <div className="w-full space-y-2">
      {/* Header row */}
      <div className="flex gap-4 pb-2 border-b">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Data rows */}
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div key={rowIdx} className="flex gap-4 py-2">
          {Array.from({ length: columns }).map((_, colIdx) => (
            <Skeleton key={colIdx} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}
```

**File 3: chart-skeleton.tsx**
```tsx
import { Skeleton } from '@/components/ui/skeleton'

interface ChartSkeletonProps {
  className?: string
  variant?: 'bar' | 'pie' | 'line'  // default 'bar'; adjusts visual shape
}

export function ChartSkeleton({ className, variant = 'bar' }: ChartSkeletonProps) {
  if (variant === 'pie') {
    return (
      <div className={`flex items-center justify-center ${className}`}>
        <Skeleton className="h-48 w-48 rounded-full" />
      </div>
    )
  }

  // bar and line share the same bar-chart skeleton appearance
  return (
    <div className={`flex items-end gap-2 h-48 ${className}`}>
      {[40, 70, 55, 90, 65, 80, 45].map((h, i) => (
        <Skeleton
          key={i}
          style={{ height: `${h}%` }}
          className="flex-1 rounded-t"
        />
      ))}
    </div>
  )
}
```

**File 4: insight-card-skeleton.tsx**
```tsx
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

interface InsightCardSkeletonProps {
  count?: number  // default 3
}

export function InsightCardSkeleton({ count = 3 }: InsightCardSkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-3">
              <Skeleton className="h-8 w-8 rounded-full" />
              <Skeleton className="h-5 w-48" />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-4 w-3/5" />
            <Skeleton className="h-6 w-32 mt-3" />
          </CardContent>
        </Card>
      ))}
    </>
  )
}
```
  </action>
  <verify>
    <automated>cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck 2>&1 | head -20</automated>
  </verify>
  <done>
    - All 4 skeleton files exist under web-app/src/components/shared/skeletons/
    - Each exports a single named function component
    - No TypeScript errors
    - All use Skeleton from @/components/ui/skeleton
  </done>
</task>

<task type="auto">
  <name>Task 2: Create ErrorBoundary class component</name>
  <files>web-app/src/components/shared/error-boundary.tsx</files>
  <action>
First, check if `react-error-boundary` is in package.json:
```bash
cat /Users/tizianoiacovelli/projects/personal-finance-app/web-app/package.json | grep react-error-boundary
```

If the package IS present: use `react-error-boundary`'s `ErrorBoundary` as the implementation (just re-export with a local `ErrorFallback` component).

If the package is NOT present (expected): create a custom class component at `web-app/src/components/shared/error-boundary.tsx`:

```tsx
'use client'

import { Component, type ReactNode, type ErrorInfo } from 'react'
import { toast } from 'sonner'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
    // toast is a regular function (not a hook) — safe to call in class lifecycle methods
    toast.error('Something went wrong. Please refresh the page.')
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="flex flex-col items-center justify-center p-8 text-center min-h-[200px]">
            <p className="text-muted-foreground text-sm">
              Something went wrong. Please refresh the page.
            </p>
          </div>
        )
      )
    }
    return this.props.children
  }
}
```

Key constraints:
- File MUST have `'use client'` directive (error boundaries must be client components in Next.js App Router)
- Class MUST NOT use any React hooks inside class methods (hooks are for function components only)
- `toast.error()` from `sonner` is a regular function — it is safe inside `componentDidCatch`
- Export as named export `ErrorBoundary` (not default export)
  </action>
  <verify>
    <automated>cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck 2>&1 | head -20</automated>
  </verify>
  <done>
    - `web-app/src/components/shared/error-boundary.tsx` exists
    - File has `'use client'` directive
    - `ErrorBoundary` is a class component extending `Component<Props, State>`
    - Implements `getDerivedStateFromError` and `componentDidCatch`
    - Accepts optional `fallback` prop
    - No TypeScript errors
  </done>
</task>

</tasks>

<verification>
After both tasks complete:
1. `cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck` — zero errors
2. All 5 files exist:
   - web-app/src/components/shared/skeletons/card-skeleton.tsx
   - web-app/src/components/shared/skeletons/table-skeleton.tsx
   - web-app/src/components/shared/skeletons/chart-skeleton.tsx
   - web-app/src/components/shared/skeletons/insight-card-skeleton.tsx
   - web-app/src/components/shared/error-boundary.tsx
3. ErrorBoundary has `'use client'` at the top
4. No skeleton file imports from recharts or any chart library
</verification>

<success_criteria>
- Four skeleton files export named components using only shadcn Skeleton primitive
- ErrorBoundary class component compiles and has correct lifecycle methods
- TypeScript compilation passes with zero errors
- No new npm packages were installed (react-error-boundary only acceptable if already in package.json)
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-foundation-02-SUMMARY.md` with:
- List of all 5 files created
- Whether react-error-boundary was found in package.json (and which implementation was used)
- TypeScript compilation status
- Any deviations from planned structure
</output>

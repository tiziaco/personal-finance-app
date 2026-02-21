# AI Agent Development Guide - Frontend

This document provides essential guidelines for AI agents working on this Next.js frontend application.

## Project Overview

This is a production-ready Next.js application built with:
- **Next.js 16.1.6** with App Router
- **Clerk** for authentication (@clerk/nextjs v6.37.3)
- **shadcn/ui** with Base UI (@base-ui/react) components
- **TypeScript** for type safety
- **Tailwind CSS** for styling

## Quick Reference: Critical Rules

### Authentication Rules
- Use **Clerk's embedded components** (custom routes) for production apps, not hosted Account Portal
- Configure environment variables to use local sign-in pages (`NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`)
- Always use Clerk middleware with `auth.protect()` to protect routes
- Trust middleware protection - if route renders, user is authenticated
- Use `useUser()` for client components, `currentUser()` for server components
- `CLERK_JWT_ISSUER_DOMAIN` is for token validation, NOT the sign-in URL

### Component Library Rules (Base UI - NOT Radix)
- **NEVER use `asChild` prop** - Base UI uses `render` prop instead
- DropdownMenuTrigger pattern: `<DropdownMenuTrigger render={<SidebarMenuButton />}>`
- **DropdownMenuLabel MUST be inside DropdownMenuGroup** (Base UI requirement)
- Check Base UI documentation, not Radix patterns

### Loading State Rules
- Use **hybrid approach**: component-level skeletons + route-level loading.tsx
- Component skeletons for: auth loading, data fetching, independent widgets
- Route-level loading.tsx for: page navigation, initial route loading
- `loading.tsx` renders ONLY in the `{children}` slot, not the entire layout
- Use sidebar-aware colors for skeletons: `bg-sidebar-accent`, `bg-muted`, or `bg-foreground/10`
- Never return `null` from loading states - return skeleton instead

### Code Style Conventions
- Use TypeScript with strict type checking
- Use `async/await` for asynchronous operations
- Prefer functional components over class components
- Use Server Components by default, Client Components only when needed (interactivity, hooks)
- File naming: kebab-case (e.g., `user-panel.tsx`, `app-sidebar.tsx`)
- Mark client components with `"use client"` directive at top of file

## Authentication Patterns

### Embedded Authentication (Current Setup)

**File Structure:**
```
app/
├── (auth)/                    # Route group for auth pages
│   ├── sign-in/[[...sign-in]]/page.tsx
│   └── sign-up/[[...sign-up]]/page.tsx
└── (app)/                     # Route group for protected app
    ├── layout.tsx             # App shell with sidebar
    ├── loading.tsx            # Route-level loading
    └── home/page.tsx
```

**Middleware Configuration:**
```typescript
// proxy.ts
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

const isPublicRoute = createRouteMatcher(['/sign-in(.*)', '/sign-up(.*)'])

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) {
    await auth.protect()  // Redirects unauthenticated users
  }
})
```

**Environment Variables:**
```env
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/home
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/home
CLERK_JWT_ISSUER_DOMAIN=https://your-instance.clerk.accounts.dev
```

### Client Component Authentication

**Hooks:** `useUser()`, `useClerk()`  
**User data:** `user.firstName`, `user.lastName`, `user.primaryEmailAddress?.emailAddress`, `user.imageUrl`  
**Actions:** `signOut()`, `openUserProfile()`  
**Loading:** Always return skeleton if `!isLoaded || !isSignedIn || !user`

### Server Component Authentication

**Functions:** `currentUser()`, `auth()`  
**Note:** Middleware already protects route, user is always authenticated

## Loading States Pattern

### Component-Level Skeletons
- Use for: auth loading, data fetching, independent widgets
- Always return skeleton instead of `null`
- Sidebar skeleton colors: `bg-sidebar-accent`, `bg-muted`, or `bg-foreground/10`

### Route-Level Loading
- Create `loading.tsx` in route folder (e.g., `app/(app)/loading.tsx`)
- Renders ONLY in `{children}` slot - layout stays mounted
- Page-specific loading overrides parent loading
- No layout shift - matches actual page padding/spacing

## Data Fetching Strategy

This template is optimized for data-heavy applications (dashboards, analytics, statistics). Use a **hybrid approach** combining Server Components with TanStack Query strategically.

### Guiding Principles

1. **Server Components First** - Default to Server Components for data fetching
2. **Client Components When Needed** - Use TanStack Query for interactivity
3. **Progressive Enhancement** - Start simple, add complexity only where needed
4. **Performance Focused** - Minimize client JavaScript, maximize server rendering

### Decision Matrix

| Scenario | Pattern | Reason |
|----------|---------|--------|
| Initial dashboard data | Server Component | Best performance, no loading states, automatic deduplication |
| Real-time updates | TanStack Query | Polling, refetching, live data |
| User filters/search | TanStack Query | Client-side state management, instant feedback |
| Static analytics | Server Component | No interactivity needed, SEO-friendly |
| Form submissions | TanStack Query (mutations) | Optimistic updates, cache invalidation |
| Paginated tables | Server Component + URL params | SEO-friendly, shareable links, browser history |
| Infinite scroll | TanStack Query (infinite query) | Client-side pagination, smooth UX |
| Charts with stable data | Server Component | Pre-rendered, no hydration cost |
| Interactive charts | Client Component + TanStack Query | User interactions, tooltips, zooming |

### Server Component Pattern (Primary)

Use Server Components for **initial data loading** and **static content**.

**Benefits:**
- Zero client-side JavaScript for data fetching
- Automatic request deduplication across components
- Better SEO and initial load performance
- No loading states needed for initial render
- Works with Next.js caching strategies (ISR, on-demand revalidation)

**Example:**
```typescript
// app/(app)/stats/page.tsx
import { getStatsData } from '@/lib/api/stats'
import { StatsChart } from '@/components/stats/stats-chart'

// Server Component (default)
export default async function StatsPage() {
  // Fetch directly in Server Component
  const stats = await getStatsData()
  
  return (
    <div className="space-y-6">
      <h1>Statistics Dashboard</h1>
      <StatsChart data={stats} />
    </div>
  )
}

// With caching
// lib/api/stats.ts
export async function getStatsData() {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/stats`, {
    headers: { Authorization: `Bearer ${await getToken()}` },
    next: { 
      revalidate: 300, // Cache for 5 minutes
      tags: ['stats'] // For on-demand revalidation
    }
  })
  return res.json()
}
```

### TanStack Query Pattern (Client Interactivity)

Use TanStack Query when you need **client-side interactivity** and **real-time updates**.

**Use Cases:**
- Real-time data updates (polling)
- Optimistic UI updates
- Client-side filtering/sorting
- Mutations with automatic cache invalidation
- Background refetching
- Retry logic with exponential backoff

**Setup:**
```typescript
// app/providers.tsx
"use client"

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useState } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            gcTime: 5 * 60 * 1000, // 5 minutes
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
```

**Example:**
```typescript
// components/stats/real-time-stats.tsx
"use client"

import { useQuery } from '@tanstack/react-query'
import { getStatsData } from '@/lib/api/stats'

export function RealTimeStats() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['stats'],
    queryFn: getStatsData,
    refetchInterval: 30000, // Poll every 30s
  })

  if (isLoading) return <Skeleton className="h-32 w-full" />
  if (error) return <div>Error loading stats</div>

  return <StatsDisplay data={data} />
}
```

### Hybrid Pattern (Recommended)

Combine both approaches for **optimal performance** on data-heavy dashboards:

```typescript
// app/(app)/dashboard/page.tsx
import { Suspense } from 'react'
import { getInitialStats } from '@/lib/api/stats'
import { StaticCharts } from '@/components/dashboard/static-charts'
import { RealTimeMetrics } from '@/components/dashboard/real-time-metrics'
import { Skeleton } from '@/components/ui/skeleton'

// Server Component
export default async function DashboardPage() {
  // Initial data fetched on server - fast first render
  const initialStats = await getInitialStats()
  
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Dashboard</h1>
      
      {/* Static charts - Server Component, no hydration cost */}
      <StaticCharts data={initialStats} />
      
      {/* Real-time data - Client Component with TanStack Query */}
      <Suspense fallback={<Skeleton className="h-64 w-full" />}>
        <RealTimeMetrics />
      </Suspense>
    </div>
  )
}
```

### API Client with Authentication

Create a centralized API client that handles Clerk authentication:

```typescript
// lib/api/client.ts
import { auth } from '@clerk/nextjs/server'

export async function apiClient(endpoint: string, options?: RequestInit) {
  const { getToken } = await auth()
  const token = await getToken()

  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options?.headers,
    },
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: 'API Error' }))
    throw new Error(error.message || `API Error: ${res.status}`)
  }

  return res.json()
}

// lib/api/stats.ts
import { apiClient } from './client'

export async function getStatsData() {
  return apiClient('/api/v1/stats')
}

export async function getTransactions(filters?: { from?: string; to?: string }) {
  const params = new URLSearchParams(filters).toString()
  return apiClient(`/api/v1/transactions?${params}`)
}
```

### Performance Optimizations

1. **Next.js Caching** - Use `next.revalidate` and `next.tags` for Server Components
2. **Suspense Boundaries** - Progressive loading with granular fallbacks
3. **Prefetching** - Use `queryClient.prefetchQuery()` for predictable navigation
4. **Parallel Fetching** - Fetch independent data in parallel within Server Components
5. **Request Deduplication** - Automatic in Server Components, manual with TanStack Query

### Common Patterns

**Server-Side Pagination (SEO-friendly):**
```typescript
// app/(app)/transactions/page.tsx
export default async function TransactionsPage({
  searchParams,
}: {
  searchParams: { page?: string }
}) {
  const page = Number(searchParams.page) || 1
  const transactions = await getTransactions({ page })
  
  return <TransactionTable data={transactions} currentPage={page} />
}
```

**Client-Side Filtering (instant feedback):**
```typescript
// components/transactions/transaction-list.tsx
"use client"

export function TransactionList() {
  const [filters, setFilters] = useState({ status: 'all' })
  
  const { data } = useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => getTransactions(filters),
  })
  
  return <div>...</div>
}
```

### When to Use Each Approach

**Use Server Components when:**
- Data is static or changes infrequently
- Initial page load performance is critical
- SEO is important
- No client-side interactivity needed
- Data doesn't depend on user interactions

**Use TanStack Query when:**
- Real-time updates required (polling)
- User interactions trigger data changes
- Need optimistic UI updates
- Client-side caching/refetching needed
- Data depends on client-side state
- Need retry logic or error recovery

**Best Practice:** Start with Server Components, add TanStack Query only where interactivity demands it. This keeps bundle size small and performance high.

## Base UI Component Patterns

### ⚠️ Critical: Base UI ≠ Radix UI

This project uses **Base UI** (@base-ui/react), NOT Radix UI. Patterns are different!

### Dropdown Menu Pattern

```tsx
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

<DropdownMenu>
  {/* ✅ CORRECT: Use render prop, not asChild */}
  <DropdownMenuTrigger render={<SidebarMenuButton />}>
    Trigger Content
  </DropdownMenuTrigger>
  
  <DropdownMenuContent>
    {/* ✅ CORRECT: Label inside Group */}
    <DropdownMenuGroup>
      <DropdownMenuLabel>Header</DropdownMenuLabel>
    </DropdownMenuGroup>
    
    <DropdownMenuItem>Item 1</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

### Common Base UI Mistakes to Avoid

```tsx
// ❌ WRONG: Using Radix pattern
<DropdownMenuTrigger asChild>
  <Button>Trigger</Button>
</DropdownMenuTrigger>

// ✅ CORRECT: Use Base UI pattern
<DropdownMenuTrigger render={<Button />}>
  Trigger
</DropdownMenuTrigger>

// ❌ WRONG: Label outside Group
<DropdownMenuContent>
  <DropdownMenuLabel>Header</DropdownMenuLabel>
</DropdownMenuContent>

// ✅ CORRECT: Label inside Group
<DropdownMenuContent>
  <DropdownMenuGroup>
    <DropdownMenuLabel>Header</DropdownMenuLabel>
  </DropdownMenuGroup>
</DropdownMenuContent>
```

## Route Organization

### Route Groups

Use `(name)` folders for organization without affecting URLs:

```
app/
├── (auth)/sign-in/, sign-up/    → /sign-in, /sign-up
├── (app)/home/, stats/           → /home, /stats  
└── (marketing)/about/, pricing/  → /about, /pricing
```

**Benefits:** Organization without URL nesting, shared layouts per group

### Root Page

```tsx
// app/page.tsx - Simply redirect authenticated users
export default function Page() {
  redirect("/home")
}
```

Middleware handles unauthenticated users automatically.

## Configuration Management

### Environment Variables

```env
# Clerk Authentication
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWT_ISSUER_DOMAIN=https://your-instance.clerk.accounts.dev

# Clerk URLs (use local pages, not hosted Account Portal)
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/home
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/home

# Application
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

**Variable Prefixes:**
- `NEXT_PUBLIC_*` - Accessible in browser
- No prefix - Server-side only

## Key Dependencies

- **Next.js 16.1.6** - React framework with App Router
- **@clerk/nextjs v6.37.3** - Authentication
- **@base-ui/react** - Headless UI components (NOT Radix)
- **shadcn/ui** - Pre-built components using Base UI
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling

## Common Pitfalls to Avoid

- ❌ Using hosted Account Portal for production (use embedded components)
- ❌ Using `asChild` prop (Base UI uses `render` prop)
- ❌ Putting DropdownMenuLabel outside DropdownMenuGroup
- ❌ Returning `null` from loading states (return skeleton)
- ❌ Creating full-page skeletons that duplicate layout structure
- ❌ Confusing `CLERK_JWT_ISSUER_DOMAIN` with sign-in URL
- ❌ Missing `"use client"` directive on client components
- ❌ Manually checking auth in protected routes (middleware handles it)
- ❌ Using wrong skeleton colors on sidebar (use `bg-sidebar-accent`)

## When Making Changes

Before modifying code:
1. Check if component needs `"use client"` directive
2. Verify Base UI patterns (not Radix) for UI components
3. Use component-level skeletons for loading states (not `null`)
4. Trust middleware for auth - no manual checks in protected routes
5. Use route groups `(name)` for organization without URL nesting
6. Create page-specific loading.tsx for unique layouts
7. Test loading states with artificial delays when needed

## Authentication Flow Summary

1. **User hits protected route** → Middleware runs
2. **Not authenticated** → Redirect to `/sign-in`
3. **Authenticated** → Route renders, user data available
4. **Sign out** → Redirect to `/sign-in` (configured in env)
5. **User profile** → `clerk.openUserProfile()` modal (embedded)

## Loading State Best Practices

**Priority (choose one):**
1. **Component-level** (80%) - Most cases, granular control
2. **Route-level loading.tsx** (15%) - Page navigation
3. **Global overlay** (5%) - Complex auth flows only

**Current Setup:**
- ✅ Component skeletons for auth and data
- ✅ Route-level loading.tsx for navigation
- ✅ No full-page skeleton (avoids layout shift)

## References

- Clerk Documentation: https://clerk.com/docs
- Next.js App Router: https://nextjs.org/docs/app
- Base UI Documentation: https://base-ui.com/ (NOT Radix UI)
- shadcn/ui Documentation: https://ui.shadcn.com/

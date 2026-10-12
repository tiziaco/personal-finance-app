# Web App — Frontend Guide

pnpm monorepo containing one Next.js 16 application (`apps/web`) backed by shared
packages. This file is the working rules; the reasoning — the access gate, the session
boundary, the path to the API — is in
[`docs/architecture/web-app.md`](../docs/architecture/web-app.md).

---

## Workspace Structure

### The three UI packages, and why they are three

They stack: `@app/core` ← `@app/ui` ← `@app/components` ← `apps/*`. The split is by
what survives a React Native port, not by taste.

- **`@app/core`** holds everything with no render dependency. It builds with
  `lib: ["esnext"]` and no `"dom"`, so `window` in its own source is a **type error** —
  that is the enforcement, not a convention. `skipLibCheck` is load-bearing alongside it
  (see the comment in its tsconfig); do not flip it off.
- **`@app/ui`** is web-only and permanently so. Base UI, DOM elements, CSS variables,
  `sonner` and `next-themes` do not run on React Native. A native target means a second
  primitives package, never an adapter for this one.
- **`@app/components`** is composed chrome that knows the app's nav shape, user model,
  branding and settings surface. It reaches for `next/image`, `next/link` and
  `usePathname`.

**`@app/components` depends on `@app/core`, `@app/ui` and `lucide-react` — and nothing
else, ever.** Its `package.json` is the boundary; a docs paragraph is not. Shared code
that needs Clerk or the API client does not go there. It goes into the package it is
already coupled to (`@app/api-client` holds `useServerStatus` and `QueryProvider`), or
it stays in the app.

Import shapes differ on purpose — the subpath should carry information:

```ts
import { Skeleton } from "@app/ui/skeleton"                         // subpath — this is the default
import { Button, Skeleton } from "@app/ui"                          // barrel — pulls all 19 primitives into the client graph; prefer the subpath
import { AppSidebar } from "@app/components/layout/app-sidebar"     // no barrel
import { cn } from "@app/core/lib/utils"                            // no barrel
import type { NavItem } from "@app/core/types/nav"
```

### Where a new component goes

Six homes, decided by what the component imports. The table, the slot pattern that promotes
a component, adding a primitive (its barrel line is by hand) and the three edits a new
package needs that fail far from their cause are in the `web-app-patterns` skill,
`references/components.md`.

The app follows the conventions, dependencies, and patterns described in this file.

---

## Dev Commands

Scripts are in `web-app/package.json`. `pnpm dev` uses the main checkout's port (3000);
from the repo root, `make dev-web` follows the checkout's own port, which differs in a git
worktree (see *Parallel worktrees* in the root `CLAUDE.md`).

---

## Lint and Format

Prettier ignores Markdown and the generated client; orval formats the latter
through the same config, so `make gen-contract` and `pnpm format` agree.

## Testing

Vitest + Testing Library in jsdom. One config, `vitest.config.mts`, with two
projects: `packages` (every `packages/*/src`) and `web`, which resolves `@/` to
`apps/web/src/`. A second app would need its own `portal(...)` line there.

The root `package.json` pins `react` and `react-dom` for the tests. **Keep them
equal to the app's exact version**: bump React in `apps/web` alone and the lockfile
holds two copies, `resolve.dedupe` sends the tests to the root one, and the suite
runs a React the app doesn't ship.

`pnpm test`, or `make test-web` from the repo root. **The pre-push hook runs it**
after `make check-web` whenever `web-app/` changed; there is no CI.

**Tests are co-located with their subjects** — `user-panel.test.tsx` next to
`user-panel.tsx` — so a test moves with `git mv` when a component is promoted
between packages. This diverges from `server/tests/` on purpose.

**`*.test.*` is Vitest. `*.spec.*` is reserved for Playwright** and excluded from
the run.

Before writing or debugging a test, read the **`/web-app-testing`** skill: the
sidebar/`matchMedia` trap, type-checked test files, the pinned `NODE_ENV`, the root React pin and
module-load constants all fail far from their cause.

## Skills to Use

Invoke these skills before starting the relevant task. The `web-app-patterns` skill's
reference files are the long form of the conventions on this page.

| Situation | Skill |
|-----------|-------|
| Adding a screen, a component or a table, wiring it to the API, any change under `apps/web/src/` or `packages/` | `/web-app-patterns` |
| Writing, running or debugging any test | `/web-app-testing` |

---

## Next.js Version Notice

This project uses **Next.js 16** — APIs and conventions may differ from training data.  
Before writing any Next.js-specific code, read the relevant guide in:

```
node_modules/next/dist/docs/
```

Heed deprecation notices. Do not assume patterns from older versions apply.

---

## Critical Rules

### Base UI (NOT Radix)

This project uses **Base UI** (`@base-ui/react`), not Radix UI. Patterns are different:

- Use `render` prop instead of `asChild`
- `DropdownMenuLabel` must be inside `DropdownMenuGroup`

```tsx
// ✅ Correct
<DropdownMenuTrigger render={<Button />}>Trigger</DropdownMenuTrigger>

// ❌ Wrong — Radix pattern, does not work here
<DropdownMenuTrigger asChild><Button>Trigger</Button></DropdownMenuTrigger>
```

### Shared Components

Before creating a new component, check the placement table in
`references/components.md` of the `web-app-patterns` skill — `packages/ui` is only the
home for shadcn/Base UI primitives.

### Server vs Client Components

- Default to **Server Components**
- Add `"use client"` only when needed: event handlers, hooks, browser APIs
- File naming: **kebab-case** (`user-panel.tsx`, `app-sidebar.tsx`)

### Authentication

- **Clerk** (`@clerk/nextjs` **v6, Core 2**) handles auth — no login/register endpoints to
  build. Use embedded Clerk components (custom routes), not the hosted Account Portal
- Client components: `useAppAuth()` from `@app/auth` — never `useUser()` / `useAuth()`.
  Check `isLoaded` before rendering the user
- Sign out with `signOut()` from `useAppAuth()`, never `useClerk().signOut`
- Trust the proxy: if a protected route renders, the user is authenticated — no manual
  checks. There are no roles and no organisations
- Auth logic lives in `packages/auth`, never `packages/ui`

The long form — the `useAppAuth()` fields, `proxy.ts`, signing out — is `references/auth.md` in the `web-app-patterns` skill.

### API Client — Generated, Never Hand-Written

Every request and response type comes from `@app/api-client`, generated by orval from
`server/openapi.json`. **A hand-written type describing an API payload is a bug.**

```typescript
import { useGetReadiness } from "@app/api-client/endpoints/system"  // hooks, per tag
import type { ReadinessResponse } from "@app/api-client/types"      // types
import { GetReadinessResponse } from "@app/api-client/zod/system"   // Zod validators
import { ApiError } from "@app/api-client"                          // the error type
```

- **Never hand-edit `packages/api-client/src/generated/`** — orval runs with `clean: true`.
- **Regenerate in the same commit as the server change**: `make gen-contract` from the
  repo root (the pre-commit hook, the image build and CI all fail on drift).
- Import hooks **per tag** (`/endpoints/<tag>`). Streaming routes have no hook — plain `fetch`.
- Generated hooks are **client-only** (`useApiFetch` is a hook); a Server Component, route
  handler or script needs a hand-written fetch. No `src/lib/api/` layer.
- Every hook's `error` is an `ApiError` — `{ status, body, requestId }`. `QueryProvider`
  toasts copy mapped from the **status**; never render `error.message` or `error.body`.

Which path to take, pagination, filters, polling and the server fetch are
`references/data-access.md` in the `web-app-patterns` skill.

### Loading States

- Use **component-level skeletons** for auth loading and data fetching
- Use **`loading.tsx`** for route-level navigation loading
- Never return `null` from loading states — always return a skeleton
- Skeleton colors: `Skeleton`'s own `bg-muted` in page content, `bg-sidebar-accent` inside the sidebar

Adding a screen — its route group, sidebar entry, loading state and copy — is
`references/pages.md` in the `web-app-patterns` skill.

### Error Handling

- API payloads are validated with the **generated Zod schemas** (`@app/api-client/zod/*`);
  hand-written schemas are only for non-API input such as forms
- Let TanStack Query's `error` state or an error boundary handle display — see the
  API Client section above for what may and may not be rendered
- Never swallow errors silently

---

## Common Pitfalls

Beyond the rules above:

- Setting `CLERK_JWT_ISSUER_DOMAIN` and expecting it to do something — nothing reads it. The issuer that anchors token validation is the **server's** `CLERK_ISSUER` (`server/app/core/config.py`, `AuthSettings`); the app only needs the publishable key and the sign-in URL
- Calling `useClerk().signOut` — a client-side route keeps the previous user's caches; use `signOut` from `useAppAuth()`
- Moving `QueryProvider` back to the root layout — the cache would outlive the session
- Putting `NODE_ENV` in an env file — Next sets it per command; anywhere else it leaks into (the root Makefile exports `apps/web/.env.local`) it decides how React builds under test

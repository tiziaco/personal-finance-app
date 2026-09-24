# Web App — Frontend Guide

pnpm monorepo containing two Next.js 16 applications backed by shared UI packages.

---

## Workspace Structure

```
web-app/
├── apps/
│   ├── internal-portal/   # Dashboard for project managers (port 3000)
│   └── supplier-portal/   # External supplier portal (port 3002)
└── packages/
    ├── api-client/        # Generated API client from the OpenAPI spec (packages/api-client)
    ├── auth/              # Role enum, useAppAuth(), getUserRole() (packages/auth)
    ├── core/              # cn(), NavItem, copy — no renderer (packages/core)
    ├── ui/                # shadcn/Base UI primitives, WEB ONLY (packages/ui)
    └── components/        # Composed chrome, built on ui (packages/components)
```

### The three UI packages, and why they are three

They stack: `@app/core` ← `@app/ui` ← `@app/components` ← `apps/*`. The split is by
what survives a React Native port, not by taste — and by what two portals can share
without pretending they are one app.

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
it stays in each portal.

Import shapes differ on purpose — the subpath should carry information:

```ts
import { Skeleton } from "@app/ui/skeleton"                         // subpath — this is the default
import { Button, Skeleton } from "@app/ui"                          // barrel — pulls all 19 primitives into the client graph; prefer the subpath
import { AppSidebar } from "@app/components/layout/app-sidebar"     // no barrel
import { cn } from "@app/core/lib/utils"                            // no barrel
import type { NavItem } from "@app/core/types/nav"
```

`@app/ui`'s `exports` is wildcard-based, so `shadcn add` needs no `package.json` edit —
but its barrel (`packages/ui/src/index.ts`) is still hand-maintained, so **a new
primitive needs a line there** or it is silently missing from `@app/ui`.

### Where a new component goes

| The component… | Goes in |
|---|---|
| has no render dependency at all | `packages/core` |
| is a shadcn/Base UI primitive | `packages/ui` |
| composes primitives, no Clerk and no API client | `packages/components` |
| is shared by both portals and needs the API client | `packages/api-client` |
| is bound to **one portal's** auth, routes or payloads | that portal's `src/components/` |
| is a shipped example a fork should **rewrite, not configure** | that portal's `src/components/`, even with no such binding |

The last row is what `general-settings.tsx` is. It imports only `@app/ui`, `next-themes`
and `lucide-react`, so the rule above says "promote" — and it stays in both portals
anyway. Its body *is* the customization, `SETTINGS_TABS` is the extension point it hangs
off, and duplicating it is the demonstration that each portal owns its settings surface.
The question that decides this row is: **does a fork configure this, or rewrite it?**

The slot pattern (`settingsSlot`, `userSlot`, `footerSlot`) is the promotion mechanism,
not just a way to avoid importing `@app/auth` into `packages/components`. When one
impure line is all that holds a component in an app, the line becomes a slot and the
component moves up.

### Failure modes with no safety net

- A new package without a matching `@source` line in **both** portals' `globals.css`
  builds clean and renders unstyled. Tailwind scans filesystem paths, not package
  graphs. Verify against `h-125` and `max-w-2xl!` in the emitted CSS — they exist
  nowhere else in the repo.
- A new primitive is importable as `@app/ui/<name>` immediately, because `exports` is a
  wildcard, but is missing from the barrel until someone edits `src/index.ts` by hand.
  That has already happened twice — `AvatarBadge` and `SidebarFooterMenu`.
- `packages/core` compiles without the `dom` lib, so the "no renderer" rule is enforced
  by `tsc` rather than by review. Worth stating, because the error it produces looks
  like a misconfiguration if you do not know it is deliberate.
- A new workspace package needs to be added to `transpilePackages` in **both** portals'
  `next.config.ts`. The packages ship raw TypeScript, so a package left out doesn't fail
  at the config — it fails as a parse error somewhere inside the package itself, with
  nothing connecting it back to `next.config.ts`.
- A new workspace package needs its `package.json` copied in `web-app/Dockerfile`'s
  deps stage, or `pnpm install --frozen-lockfile` fails in the container and nowhere
  else.

Both apps share the same conventions, dependencies, and patterns described in this file.

---

## Dev Commands

Run from `web-app/`:

```bash
pnpm install               # install all workspace dependencies

pnpm dev:internal          # internal-portal → http://localhost:3000
pnpm dev:supplier          # supplier portal  → http://localhost:3002

pnpm build                 # build all apps
pnpm type-check            # TypeScript check across workspace
```

3000 and 3002 are the main checkout's defaults. From the repo root,
`make dev-internal` / `make dev-supplier` follow the checkout's own ports, which
differ in a git worktree (see *Parallel worktrees* in the root `CLAUDE.md`).

Env files must exist before starting:

```bash
cp apps/internal-portal/.env.example apps/internal-portal/.env.local
cp apps/supplier-portal/.env.example apps/supplier-portal/.env.local
```

---

## Lint and Format

```bash
pnpm lint            # ESLint in both portals and in packages/ui, packages/auth
pnpm format          # Prettier --write (config: .prettierrc, semicolons off)
pnpm format:check    # what the root pre-push hook runs
```

Prettier ignores Markdown and the generated client; orval formats the latter
through the same config, so `make gen-contract` and `pnpm format` agree.

## Skills to Use

Invoke these skills before starting the relevant task:

| Situation | Skill |
|-----------|-------|
| Designing or building any UI — layouts, components, pages, visual hierarchy | `/frontend-design` |
| Deciding where/how to fetch data from the API | `/nextjs-data-fetching-strategy` |
| Building or refactoring React components | `/react` |
| Adding auth, handling user input, or touching security-sensitive code | `/security-review` |
| Performance optimization — bundle size, rendering, caching | `/vercel-react-best-practices` |

---

## Next.js Version Notice

This project uses **Next.js 16** — APIs and conventions may differ from training data.  
Before writing any Next.js-specific code, read the relevant guide in:

```
node_modules/next/dist/docs/
```

Heed deprecation notices. Do not assume patterns from older versions apply.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | Next.js 16 + React 19, App Router |
| Language | TypeScript 5 (strict) |
| Styling | Tailwind CSS v4 |
| UI Components | shadcn/ui + **Base UI** (`@base-ui/react`) + Lucide React |
| Auth | Clerk (`@clerk/nextjs`) |
| Data Fetching | TanStack Query v5 — hooks generated by orval (`@app/api-client`) |
| Validation | Zod v4 |
| Notifications | Sonner |
| Package Manager | pnpm (workspaces) |

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

Before creating a new component, check the placement table in "Where a new component
goes" above — there are five candidate homes now, and `packages/ui` is only the one for
shadcn/Base UI primitives.

### Server vs Client Components

- Default to **Server Components**
- Add `"use client"` only when needed: event handlers, hooks, browser APIs
- File naming: **kebab-case** (`user-panel.tsx`, `app-sidebar.tsx`)

### Authentication

- **Clerk** handles auth — no login/register endpoints to build
- Client components: `useAppAuth()` from `@app/auth` — never `useUser()` / `useAuth()` directly. Server components: `currentUser()`
- Trust middleware: if a protected route renders, the user is authenticated — no manual auth checks needed
- Use embedded Clerk components (custom routes), not hosted Account Portal

### Clerk RBAC — Auth Package and Role-Gated Rendering

Shared auth logic lives in **`packages/auth`** (`@app/auth`) — not in `packages/ui`. This includes the `Role` enum, `getUserRole()`, `isInternalRole()`, `ROLE_LABELS`, and the `AuthProvider` / `useAppAuth()` hook.

This project is on `@clerk/nextjs` **v6 (Core 2)**. The current SDK (`<Show>`) is not available.

**In client components — always use `useAppAuth()`**, never `useAuth()` or `useUser()` directly:

```typescript
import { useAppAuth, Role } from '@app/auth'

const { user, role, isLoaded } = useAppAuth()
if (role === Role.PROJECT_MANAGER) { ... }
```

**Declarative role gates — use `<Protect>`** from `@clerk/nextjs` (Core 2):

```tsx
import { Protect } from '@clerk/nextjs'

<Protect role="org:project_manager">
  <InviteButton />
</Protect>
```

**Middleware (`proxy.ts`):** read `orgRole` from `auth()` and pass through `getUserRole()` from `@app/auth`:

```typescript
import { getUserRole, isInternalRole } from '@app/auth'

// correct
const { orgRole } = await auth()
const role = getUserRole(orgRole)

// wrong — reads user metadata, not org role
const { sessionClaims } = await auth()
const role = sessionClaims?.metadata?.role
```

### API Client — Generated, Never Hand-Written

Every request and response type comes from `@app/api-client`, generated by orval from
`server/openapi.json`. **A hand-written type describing an API payload is a bug.**

```typescript
import { useGetReadiness } from "@app/api-client/endpoints/system"  // hooks, per tag
import type { ReadinessResponse } from "@app/api-client/types"      // types
import { GetReadinessResponse } from "@app/api-client/zod/system"   // Zod validators
import { ApiError } from "@app/api-client"                          // the error type
```

Rules:

- **Never hand-edit anything under `packages/api-client/src/generated/`.** orval runs
  with `clean: true` and deletes that tree on every generation.
- **Regenerate in the same commit as the server change.** Run `make gen-contract` from
  the repo root, or the **Contract: Generate** VS Code task. `make check-contract` does
  the same and then fails on drift — that is what CI and the image build run, and the
  pre-commit hook blocks a `server/app/` commit that leaves the artifacts behind.
- Import hooks **per tag** (`/endpoints/<tag>`), not from a barrel. Tags come from the
  route's FastAPI tag.
- Streaming routes are deliberately excluded from generation (they carry the `streaming`
  tag), so they have no hook. Call them with plain `fetch`.
- Generated hooks route through `useApiFetch`, which is **a hook** — it reads the live
  Clerk token from `useAppAuth()` on every call. That makes them client-only: a Server
  Component, route handler or script needs its own hand-written fetch.
- Do not create an `src/lib/api/` layer. The generated client is that layer.

**Errors.** Every hook's `error` is an `ApiError` — `{ status, body, requestId }` — and
nothing else. `QueryProvider` (`@app/api-client`) toasts centrally, mapping the
**status** to curated copy in `@app/core`'s `constants/messages.ts`.

```typescript
// ✅ Correct — a status maps to copy we wrote
if (error.status === 404) toast.error(messages.toasts.notFound)

// ❌ Wrong — server-authored text must never reach the UI
toast.error(error.message)
toast.error(String(error.body))
```

### Loading States

- Use **component-level skeletons** for auth loading and data fetching
- Use **`loading.tsx`** for route-level navigation loading
- Never return `null` from loading states — always return a skeleton
- Use sidebar-aware skeleton colors: `bg-sidebar-accent`, `bg-muted`, `bg-foreground/10`

### Error Handling

- API payloads are validated with the **generated Zod schemas** (`@app/api-client/zod/*`);
  hand-written schemas are only for non-API input such as forms
- Let TanStack Query's `error` state or an error boundary handle display — see the
  API Client section above for what may and may not be rendered
- Never swallow errors silently

---

## Common Pitfalls

- Using `asChild` (Radix) instead of `render` prop (Base UI)
- Placing `DropdownMenuLabel` outside `DropdownMenuGroup`
- Creating new components in `apps/` that belong in one of the shared packages — see
  "Where a new component goes" above
- Returning `null` from loading states
- Using wrong skeleton colors inside sidebars
- Forgetting `"use client"` on components with hooks or event handlers
- Setting `CLERK_JWT_ISSUER_DOMAIN` and expecting it to do something — nothing reads it. The issuer that anchors token validation is the **server's** `CLERK_ISSUER` (`server/app/core/config.py`, `AuthSettings`); the portals only need the publishable key and the sign-in/sign-up URLs
- Using `<Show when={{ role }}>` (current SDK) instead of `<Protect role="org:...">` (Core 2 / v6)
- Reading `sessionClaims.metadata.role` for role checks — use `auth().orgRole` instead
- Calling `useAuth()` / `useUser()` directly in components — use `useAppAuth()` from `@app/auth`
- Calling `has({ role: "org:..." })` directly in components — use `role === Role.*` from `useAppAuth()`
- Putting auth logic in `packages/ui` — it belongs in `packages/auth`
- Hand-editing files under `packages/api-client/src/generated/` — the next generation deletes them
- Hand-writing a type for a request or response body — import it from `@app/api-client/types`
- Changing a server route without running `make gen-contract` in the same commit
- Rendering `error.message` or `error.body` — map `error.status` to copy in `@app/core`'s `constants/messages.ts`

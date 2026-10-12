# Internal Portal

The template's internal portal — the app staff sign in to. In the shipped example domain it manages projects, suppliers, purchase orders and document compliance tracking.

Runs on **http://localhost:3000** in the main checkout; `make dev-internal` from the repo
root follows the checkout's own port, which differs in a git worktree.

---

## Overview

This is a [Next.js 16](https://nextjs.org/) application using the App Router, part of the `web-app` pnpm monorepo.

**Routes:**

| Route | Description |
|---|---|
| `/home` | Placeholder page in `src/app/(dashboard)/` — finance screens are not built yet |
| `/sign-in` | Clerk's sign-in |
| `/sign-up` | Clerk's sign-up — public; the first request provisions the account |

---

## Getting Started

### 1. Set up environment variables

```bash
cp .env.example .env.local
```

Edit `.env.local` and fill in your Clerk API keys and other required values:

```env
NEXT_PUBLIC_API_URL=http://localhost:8100

NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...

NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/home
```

The `NEXT_PUBLIC_CLERK_*` values are read by the Clerk SDK straight from the
environment, not by any code in this repo — so grepping for them finds only config and
docs.

The `NEXT_PUBLIC_*` values are **inlined at image build time**, not read at runtime, so
changing one means rebuilding the image.

Getting the keys is only half of it — this portal's origin must be listed in the server's
`ALLOWED_ORIGINS`. See [`docs/setup/clerk.md`](../../../docs/setup/clerk.md).

### 2. Install dependencies

From the `web-app/` directory:

```bash
pnpm install
```

### 3. Run the dev server

```bash
# from web-app/
pnpm dev:internal

# or from this directory
pnpm dev
```

The app will be available at http://localhost:3000.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 16, React 19, App Router |
| Language | TypeScript 5 (strict) |
| Styling | Tailwind CSS v4 |
| UI Components | shadcn/ui + Base UI (`@base-ui/react`) + Lucide React |
| Auth | Clerk (`@clerk/nextjs` v6) |
| Data Fetching | TanStack Query v5 |
| Validation | Zod v4 |
| Notifications | Sonner |

---

## Project Structure

```
src/
├── app/
│   ├── (dashboard)/   # Signed-in routes, their layout (sidebar, QueryProvider)
│   ├── (auth)/        # sign-in, sign-up
│   └── layout.tsx     # Root layout — metadata, Clerk and AuthProvider, theme
├── components/
│   ├── layout/        # This portal's user panel
│   └── settings/      # This portal's settings tabs and server-status wrapper
├── lib/               # Navigation items
├── proxy.ts           # Clerk middleware — the role gate
└── styles/            # Global CSS, and the @source lines for the shared packages
```

Shared UI lives in the workspace packages, not here — see `web-app/CLAUDE.md`'s "Where a
new component goes".

### Branding

Two files carry the visual identity — swap them for your own:

| File | Used by |
|---|---|
| `public/images/logo-small.png` | the sidebar mark, via `logoSrc` on `AppSidebar` (`@app/components`, `packages/components/src/layout/company-logo.tsx`) |
| `public/icons/favicon.ico` | the browser tab, via `metadata.icons` in `src/app/layout.tsx` |

The accompanying `logoAlt` and `metadata.title` strings live in
`src/app/(dashboard)/layout.tsx` and `src/app/layout.tsx`.

---

## Auth

Authentication is handled by Clerk. There are no organisations or roles: the signed-in user is the tenant. Components read identity through `@app/auth`:

```typescript
import { useAppAuth } from '@app/auth'

const { user, isLoaded } = useAppAuth()
```

---

## Shared Packages

- **`@app/core`** — `cn()`, `NavItem`, shared copy — no render dependency
- **`@app/ui`** — shadcn/Base UI primitives, web-only
- **`@app/components`** — composed chrome (sidebar, settings dialog) built on `@app/ui`
- **`@app/auth`** — `useAppAuth()`, `AuthProvider`
- **`@app/api-client`** — generated API client (types, endpoints, hooks) from the OpenAPI spec

See `web-app/CLAUDE.md`'s "Where a new component goes" table before creating new
components — there are five candidate homes now, not just `packages/ui`.

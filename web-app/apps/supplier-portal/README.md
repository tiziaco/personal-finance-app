# Supplier Portal

The template's external-facing portal — the app partners sign in to. In the shipped example domain suppliers use it to upload required documents, track submission status, and receive notifications on document compliance.

Runs on **http://localhost:3002**.

---

## Overview

This is a [Next.js 16](https://nextjs.org/) application using the App Router, part of the `web-app` pnpm monorepo.

**Key pages:**

| Route | Description |
|---|---|
| `/home` | Supplier dashboard |
| `/projects` | Projects the supplier is associated with |
| `/orders` | Purchase orders requiring documentation |
| `/sign-in` | Clerk-powered sign-in |
| `/sign-up` | Clerk-powered sign-up |
| `/unauthorized` | Shown to a signed-in user without supplier-portal access |

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
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/home
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/home
```

The `NEXT_PUBLIC_CLERK_*` values are read by the Clerk SDK straight from the
environment, not by any code in this repo — so grepping for them finds only config and
docs.

The `NEXT_PUBLIC_*` values are **inlined at image build time**, not read at runtime, so
changing one means rebuilding the image. Note that today both portal images are built
with the *internal* portal's build args — see
[`docs/setup/making-it-yours.md`](../../../docs/setup/making-it-yours.md).

Getting the keys is only half of it — Clerk also needs Organizations enabled, four org
roles created with exact slugs, and this portal's origin (`http://localhost:3002`) listed
in the server's `ALLOWED_ORIGINS`. See [`docs/setup/clerk.md`](../../../docs/setup/clerk.md).

### 2. Install dependencies

From the `web-app/` directory:

```bash
pnpm install
```

### 3. Run the dev server

```bash
# from web-app/
pnpm dev:supplier

# or from this directory
pnpm dev
```

The app will be available at http://localhost:3002.

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
│   ├── (app)/         # Authenticated routes (home, projects, orders)
│   ├── (auth)/        # Auth routes (sign-in, sign-up)
│   ├── layout.tsx     # Root layout
│   └── unauthorized/  # Wrong-role landing page
├── components/
│   ├── layout/        # Sidebar, header, shell components
│   ├── settings/      # Settings UI
│   └── ui/            # Page-level UI components
├── hooks/             # Custom React hooks
├── lib/               # Utilities, API helpers, env config
├── providers/         # React context providers
├── proxy.ts           # Clerk middleware / RBAC proxy
└── styles/            # Global CSS
```

### Branding

Two files carry the visual identity — swap them for your own:

| File | Used by |
|---|---|
| `public/images/logo-small.png` | the sidebar mark, via `logoSrc` on `AppSidebar` (`@app/components`, `packages/components/src/layout/company-logo.tsx`) |
| `public/icons/favicon.ico` | the browser tab, via `metadata.icons` in `src/app/layout.tsx` |

The accompanying `logoAlt` and `metadata.title` strings live in
`src/app/(portal)/layout.tsx` and `src/app/layout.tsx`. This portal's assets are
separate from the internal portal's on purpose — the two deploy as distinct images and
can carry distinct branding.

---

## Auth & Roles

Authentication is handled by Clerk. Role-based access control uses org roles mapped through `@app/auth`:

```typescript
import { useAppAuth, Role } from '@app/auth'

const { user, role, isLoaded } = useAppAuth()
if (role === Role.SUPPLIER) { ... }
```

Use `<Protect role="org:supplier">` from `@clerk/nextjs` for declarative role gates.

---

## Shared Packages

- **`@app/core`** — `cn()`, `NavItem`, shared copy — no render dependency
- **`@app/ui`** — shadcn/Base UI primitives, web-only
- **`@app/components`** — composed chrome (sidebar, settings dialog) built on `@app/ui`
- **`@app/auth`** — `Role` enum, `useAppAuth()`, `getUserRole()`
- **`@app/api-client`** — generated API client (types, endpoints, hooks) from the OpenAPI spec

See `web-app/CLAUDE.md`'s "Where a new component goes" table before creating new
components — there are five candidate homes now, not just `packages/ui`.

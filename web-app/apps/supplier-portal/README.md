# Supplier Portal

External-facing portal for Rilevio suppliers. Allows suppliers to upload required documents, track submission status, and receive notifications on document compliance.

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

---

## Getting Started

### 1. Set up environment variables

```bash
cp .env.example .env.local
```

Edit `.env.local` and fill in your Clerk API keys and other required values:

```env
NEXT_PUBLIC_APP_URL=http://localhost:3002
NEXT_PUBLIC_API_URL=http://localhost:8000

NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWT_ISSUER_DOMAIN=https://....clerk.accounts.dev
```

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
│   └── page.tsx       # Root redirect
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

- **`@app/ui`** — shared shadcn/ui components
- **`@app/auth`** — `Role` enum, `useAppAuth()`, `getUserRole()`
- **`@app/types`** — shared TypeScript types

Always check `packages/ui` before creating new components.

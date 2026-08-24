# Web App Monorepo Design

**Date:** 2026-04-09
**Status:** Approved
**Scope:** Initialise the `web-app/` workspace with two Next.js applications and shared packages using pnpm workspaces (no Turborepo).

---

## Context

Rilevio requires two client-facing web applications backed by a single FastAPI server:

- **`internal-portal`** — internal dashboard for project managers and other internal departments to manage projects, suppliers, orders, and document compliance
- **`supplier-portal`** — external-facing portal where suppliers upload documents, track submission status, and receive notifications

Both apps share the same design language (Tailwind CSS v4, shadcn/ui) and a moderate-to-heavy set of UI primitives, but have distinct layouts, components, and user flows.

---

## Approach

pnpm workspaces with two standalone Next.js apps and two shared packages. No Turborepo — overkill for a solo prototype. Can be added later when the team grows.

---

## Repository Structure

```
rilevio-app/
├── web-app/
│   ├── apps/
│   │   ├── internal-portal/       # Internal dashboard (PMs, departments)
│   │   │   ├── app/               # Next.js App Router pages
│   │   │   ├── components/        # Internal-only components
│   │   │   ├── package.json
│   │   │   └── next.config.ts
│   │   └── supplier-portal/       # Supplier-facing app
│   │       ├── app/
│   │       ├── components/
│   │       ├── package.json
│   │       └── next.config.ts
│   ├── packages/
│   │   ├── ui/                    # Shared primitives only
│   │   │   ├── src/
│   │   │   │   ├── components/    # Button, Badge, Modal, Input, etc.
│   │   │   │   ├── lib/           # cn() utility, shared Tailwind helpers
│   │   │   │   └── index.ts
│   │   │   └── package.json
│   │   └── types/                 # Shared domain types
│   │       ├── src/
│   │       │   ├── project.ts     # Project, ProjectStatus
│   │       │   ├── supplier.ts    # Supplier, SupplierRole
│   │       │   ├── document.ts    # Document, DocumentStatus, DocumentType
│   │       │   ├── order.ts       # PurchaseOrder
│   │       │   └── index.ts
│   │       └── package.json
│   └── pnpm-workspace.yaml
├── server/                        # FastAPI backend (unchanged)
├── docker-compose.yml
└── Makefile
```

---

## pnpm Workspace Config

`web-app/pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

### Package naming convention

All packages use the `@rilevio/` scope:

| Directory | Package name |
|---|---|
| `packages/ui` | `@rilevio/ui` |
| `packages/types` | `@rilevio/types` |
| `apps/internal-portal` | `@rilevio/internal-portal` |
| `apps/supplier-portal` | `@rilevio/supplier-portal` |

### Workspace dependency declaration

Apps reference shared packages via the workspace protocol in their `package.json`:

```json
{
  "dependencies": {
    "@rilevio/ui": "workspace:*",
    "@rilevio/types": "workspace:*"
  }
}
```

### Dev workflow

From `web-app/`:

```bash
pnpm install                          # installs all workspaces
pnpm --filter internal-portal dev     # run internal portal
pnpm --filter supplier-portal dev     # run supplier portal
```

---

## Shared Packages

### `@rilevio/types`

Pure TypeScript, no runtime dependencies. Contains domain types shared across both apps. May also be referenced by the server layer in the future.

Types to define initially:
- `Project`, `ProjectStatus`
- `Supplier`, `SupplierRole`
- `Document`, `DocumentStatus`, `DocumentType`
- `PurchaseOrder`

### `@rilevio/ui`

Shared UI primitives only — not a full component library. Contains shadcn/ui components re-exported with the shared Tailwind config applied, plus any cross-app primitives built on top (e.g. `StatusBadge` mapping `DocumentStatus` to color variants).

**Rule:** if a component only appears in one app, it stays in that app's `components/` folder. Move to `packages/ui` only when duplication across apps is clear.

---

## Auth Strategy

One Clerk application, one publishable key, shared across both apps. User type is stored in Clerk's `publicMetadata`:

```json
{ "role": "internal" }
```

or

```json
{ "role": "supplier" }
```

Each app's Next.js middleware enforces role-based access at the route level, redirecting users who don't belong. No separate Clerk frontend API clients for now — straightforward to add per-domain JWT audiences later if needed.

---

## Tech Stack (both apps)

| Layer | Technology |
|---|---|
| Framework | Next.js 16 + React 19 |
| Language | TypeScript 5 |
| Styling | Tailwind CSS v4 |
| UI Components | shadcn/ui + Base UI + Lucide React |
| Auth | Clerk (`@clerk/nextjs`) |
| Data Fetching | TanStack Query v5 |
| Validation | Zod v4 |
| Notifications | Sonner |

---

## What's Out of Scope

- Turborepo (add when team grows)
- Separate Clerk frontend API clients per domain (add if security requirements increase post-prototype)
- Separate deployments per app are supported by the structure but not required for the prototype

# Rilevio — Web App

pnpm monorepo containing two Next.js frontend apps for the Rilevio document compliance platform.

## Structure

```
web-app/
├── apps/
│   ├── internal-portal/   # Dashboard for project managers (port 3000)
│   └── supplier-portal/   # Supplier-facing portal (port 3002)
└── packages/
    ├── auth/              # @app/auth — Role enum, useAppAuth(), getUserRole()
    ├── types/             # @app/types — shared TypeScript types
    └── ui/                # @app/ui — shared UI utilities (cn())
```

## Tech Stack

- **Next.js 16** + React 19 + TypeScript 5
- **Tailwind CSS v4** + shadcn/ui
- **Clerk** for authentication (`@clerk/nextjs`)
- **TanStack Query v5** for data fetching and caching
- **Zod v4** for schema validation
- **Sonner** for toast notifications
- **pnpm workspaces** for monorepo management

## Setup

```bash
# From web-app/
pnpm install

# Copy and fill in environment variables for each app
cp apps/internal-portal/.env.example apps/internal-portal/.env.local
cp apps/supplier-portal/.env.example apps/supplier-portal/.env.local
```

Key variables in each `.env.local`:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=...
CLERK_SECRET_KEY=...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Development Commands

```bash
# From web-app/
pnpm dev:internal    # internal dashboard at http://localhost:3000
pnpm dev:supplier    # supplier portal at http://localhost:3002
pnpm build           # production build for all apps
pnpm type-check      # TypeScript check across all packages
```

## Managing Packages

### Where to add a dependency

| Dependency type | Where to add |
|-----------------|--------------|
| Runtime dep used by one app | That app only |
| Runtime dep used by both apps | Each app individually |
| Pure UI wrapper / zero-config provider | `packages/ui` |
| Tooling (eslint, typescript, etc.) | Workspace root (`-w`) |

```bash
# Add to a specific app
pnpm --filter internal-portal add <package>
pnpm --filter supplier-portal add <package>

# Add to the shared UI package
pnpm --filter @app/ui add <package>

# Add to the workspace root (tooling only)
pnpm add -w <package>
```

Even if both apps depend on the same package at the same version, pnpm installs it once — declaring it in two `package.json` files doesn't mean duplicating it on disk.

### Adding shadcn components

shadcn components that are shared belong in `packages/ui`. Run from that directory:

```bash
cd packages/ui && pnpm dlx shadcn@latest add button dialog table
```

Components land in `packages/ui/src/components/ui/` and are exported from `packages/ui/src/index.ts`. Import them in apps via `@app/ui`.

If a component is only used in one app, add it directly inside that app instead.

## Docker Commands

```bash
make docker-build   # build Docker image
make docker-run     # run container on port 3000
make docker-stop    # stop and remove container
make docker-logs    # follow container logs
make docker-clean   # stop, remove container and image
```

> For running the full stack (frontend + backend + db), use the root `Makefile`. See the root `README.md`.

# Personal Finance — Web App

pnpm monorepo containing the Next.js app (`apps/web`) and the packages it is built from,
including one generated API client.

## Structure

```
web-app/
├── apps/
│   └── web/               # The app (port 3000)
└── packages/
    ├── api-client/        # @app/api-client — generated API client from the OpenAPI spec
    ├── auth/              # @app/auth — AuthProvider, useAppAuth(), AppUser
    ├── core/              # @app/core — cn(), NavItem, copy — no renderer
    ├── ui/                # @app/ui — shadcn/Base UI primitives, WEB ONLY
    ├── components/        # @app/components — composed chrome, built on ui
    └── data-table/        # @app/data-table — tables, filters, URL list state
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

# Copy and fill in environment variables
cp apps/web/.env.example apps/web/.env.local
```

Key variables in `.env.local`:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=...
CLERK_SECRET_KEY=...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_API_URL=http://localhost:8100
```

## Development Commands

```bash
# From web-app/
pnpm dev             # the app at http://localhost:3000
pnpm build           # production build
pnpm type-check      # TypeScript check across all packages
```

3000 is the main checkout's default. From the repo root, `make dev-web` follows the
checkout's own port, which differs in a git worktree.

## Managing Packages

### Where to add a dependency

| Dependency type | Where to add |
|-----------------|--------------|
| Runtime dep used by the app | `apps/web` |
| Needed by a primitive | `packages/ui` |
| Needed by composed chrome | `packages/components` |
| Needed by the tables or list state | `packages/data-table` |
| Pure helper, type or constant — no rendering | `packages/core` |
| Tooling (eslint, typescript, etc.) | Workspace root (`-w`) |

```bash
# Add to the app
pnpm --filter web add <package>

# Add to the shared UI package
pnpm --filter @app/ui add <package>

# Add to the workspace root (tooling only)
pnpm add -w <package>
```

### Adding shadcn components

shadcn components that are shared belong in `packages/ui`. Install each one by hand from
its page on `ui.shadcn.com/docs/components/base/` (the **Manual** tab, Base UI variant) — the
`shadcn` CLI cannot resolve the `@app/core/lib/utils` alias this workspace uses.

Components land in `packages/ui/src/primitives/` and are importable as `@app/ui/<name>`
immediately — the `exports` map is a wildcard. They are **not** in the `@app/ui` barrel
until you add a line to `packages/ui/src/index.ts` by hand.

Every primitive goes there, even one used by a single page. Composed components have their
own homes; see `references/components.md` in the `web-app-patterns` skill.

## Docker Commands

```bash
make docker-build   # build Docker image
make docker-run     # run container on port 3000
make docker-stop    # stop and remove container
make docker-logs    # follow container logs
make docker-clean   # stop, remove container and image
```

> For running the full stack (frontend + backend + db), use the root `Makefile`. See the root `README.md`.

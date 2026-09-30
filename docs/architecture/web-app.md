# Web app — the portals, the packages, and the session

How `web-app/` is put together: two Next.js portals over six shared packages, where
access is decided, how a request reaches the API, and what a third portal costs. This
describes the system as it stands and is kept current. The working rules — which
package a component goes in, import shapes, the failure modes with no safety net — are
in [`web-app/CLAUDE.md`](../../web-app/CLAUDE.md) and the `web-app-patterns` skill, and
are not repeated here.

---

## 1. Shape

Two applications and six packages in one pnpm workspace:

```
web-app/
├── apps/
│   ├── internal-portal/    # staff: project_manager, reviewer, approver
│   └── supplier-portal/    # external partners: supplier
└── packages/
    ├── core/               # @app/core        — no renderer: cn(), NavItem, copy, env flags
    ├── ui/                 # @app/ui          — shadcn/Base UI primitives, web only
    ├── components/         # @app/components  — composed chrome: sidebar, user panel, settings
    ├── data-table/         # @app/data-table  — the two tables, filters, URL list state (nuqs)
    ├── auth/               # @app/auth        — Role, AppUser, AuthProvider, useAppAuth
    └── api-client/         # @app/api-client  — generated hooks, types and Zod, plus the mutator
```

**Two portals, not one app with role-based routing.** The audiences never share a
screen: a supplier must not load the internal portal's code, and each portal deploys to
its own hostname behind its own Traefik router. They share one Clerk instance, one API
and every package. A portal is a thin shell — route groups, a nav list, a user panel,
settings tabs — and everything reusable lives in a package.

**The packages are cut by render dependency:** `core` has none, `ui` is web-only
primitives, `components` is composed chrome built from them. `auth`, `api-client` and
`data-table` are cut by concern.

**The packages import downward only:**

```
apps/*  →  components  →  ui  →  core
apps/*  →  data-table  →  ui, core
apps/*  →  api-client  →  auth, core
apps/*  →  auth
```

`components` depends on `core`, `ui` and `lucide-react` and nothing else; what needs
Clerk or the API reaches it through a slot (`userSlot`, `settingsSlot`, `footerSlot`).
`api-client` depends on `auth` for the token and on `core` for copy. `data-table` owns
TanStack Table and nuqs, so a portal reaches both only through it; it does not fetch — a
table's rows come from the portal's generated hook. Only two of these
rules are mechanical: `core` compiles without the `dom` lib, so a `window` in it is a
type error, and each package's `package.json` is the only list of what it may import.
The rest is review — the `web-app-patterns` skill's `references/components.md` lists
the edits that fail far from their cause.

## 2. A portal

```
apps/<portal>/src/
├── proxy.ts                         # the access gate (§3)
├── app/
│   ├── layout.tsx                   # ClerkProvider › AuthProvider › ThemeProvider, Toaster
│   ├── (auth)/sign-in/…             # public; the internal portal also has sign-up
│   ├── (dashboard)/ or (portal)/    # the signed-in shell
│   │   ├── layout.tsx               # QueryProvider › UrlStateAdapter › SidebarProvider › AppSidebar
│   │   └── home/, projects/, orders/
│   └── unauthorized/page.tsx        # signed in, wrong role
├── components/                      # ClerkUserPanel, GeneralSettings, ServerHealthIndicator
└── lib/hub-nav.ts                   # the sidebar's NavItem list
```

The root layout holds what every route needs, signed in or not. The route group's
layout holds the shell and the query cache — which is the point of §4. The pages under
the shell are placeholders: they are where a fork's domain starts.

The three files in `components/` are near-identical across the portals on purpose.
Each is either bound to that portal's auth (`ClerkUserPanel`) or an example a fork
rewrites rather than configures (`GeneralSettings`); the `web-app-patterns` skill's
`references/components.md` has the rule.

The supplier portal has no sign-up page: suppliers are meant to enter by invitation. Nothing
enforces that yet — see [`../TODO.md`](../TODO.md).

## 3. Who gets in

`src/proxy.ts` — Next 16's name for middleware — runs before every non-static request:

1. `/` redirects to `/home` here, not in a page: a page-level `redirect()` deadlocks the
   App Router during the navigation that follows Clerk's `setActive()`.
2. Sign-in and sign-up pass.
3. `auth.protect()` sends anyone without a session to sign-in.
4. The role comes from `auth().orgRole` through `getUserRole()`. The internal portal
   admits `isInternalRole`, the supplier portal `isSupplierRole`; anyone else — a null
   role mid-invitation included — goes to `/unauthorized`.
5. `/unauthorized` sits outside the role guard, or it would redirect to itself. A user
   who does have access is sent home from it.

This gate decides which screens render. It is not what protects data: the API
authorizes every request on its own, from the token (`docs/architecture/authorization.md`).
A route that renders can trust that a session exists and never re-checks it.

## 4. The session boundary

`@app/auth` is the only place the web app reads Clerk's session, and it exposes no
Clerk type. `useAppAuth()` returns:

| Field | What it is |
|---|---|
| `user` | `AppUser` — `name`, `email`, `imageUrl`, each `null` when absent — or `null` while loading or signed out |
| `role` | `Role` or `null`, from the active organization |
| `isLoaded` | Clerk has resolved |
| `getToken` | the session token, fresh on every call |
| `signOut` | ends the session, then loads `signOutUrl` as a new document |

Two decisions keep one user's data from reaching the next person at the same browser:

- **`QueryProvider` lives in the signed-in route group's layout, not the root.** Leaving
  the group unmounts the provider and drops the cache with it.
- **`signOut()` always ends with `window.location.assign(signOutUrl)`, in a `finally`.**
  A client-side navigation keeps React state, module state and anything a component
  cached; a new document keeps none of it. The `finally` means a failed `endSession`
  still leaves the page.

`@app/auth` also holds `ROLE_LABELS`, the roles' display labels. Nothing renders a role
yet, so only its test reads it.

`useClerk()` is used only to open Clerk's own profile and organization modals. Anything
else from Clerk goes through `@app/auth`, so a change of provider touches one package.

## 5. Talking to the API

The browser calls the API directly, cross-origin — there is no Next.js proxy hop. So
every portal origin must be in the server's `ALLOWED_ORIGINS`
([`setup/clerk.md`](../setup/clerk.md) §4). How the token itself is verified is
[`authentication.md`](./authentication.md).

```
component
  → generated hook               @app/api-client/endpoints/<tag>
  → useApiFetch                  base URL, Bearer token, ApiError
  → FastAPI
  → QueryProvider                cache, retry, toast
```

- **The client is generated** from the committed `server/openapi.json` by orval — hooks
  per tag, types, Zod schemas. Nothing under `generated/` is edited by hand, and a
  hand-written payload type is a bug. The pipeline and its traps are in
  [`api-client-codegen.md`](../guides/api-client-codegen.md).
- **`useApiFetch` is a hook, not a module-level client.** It reads the token on every
  call, so no request can carry another session's token, and it needs no provider. The
  cost: generated hooks run only in client components. A Server Component or route
  handler that needs the API writes its own `fetch`.
- **Every failure is an `ApiError`** — `status`, `body`, `requestId`. The message never
  carries server text.
- **`QueryProvider` owns the error policy.** A query toasts only if it has never
  resolved, so a failing background refetch behind visible data stays quiet, and
  `meta: { silentError: true }` opts a query out. A mutation always toasts. The toast
  maps `status` to copy in `@app/core`'s `constants/messages.ts`; server text never
  reaches the UI. A 4xx is not retried.
- **Reading an error body goes through the generated Zod schema.** `useServerStatus` is
  the example: `/ready` answers 503 with a valid payload when degraded, which arrives as
  `ApiError.body`. The hook parses it with `GetReadinessResponse` and prefers it over
  the stale `data` the cache still holds.

## 6. Configuration and build

Each portal reads its own `apps/<portal>/.env.local`. `NEXT_PUBLIC_*` values are inlined
at build time, so an image is built for one API URL and one Clerk instance.

One `web-app/Dockerfile` builds either portal, selected by the `APP_NAME` build arg, as
a standalone Next.js server listening on 3000. `next.config.ts` lists every workspace
package in `transpilePackages` — they ship raw TypeScript — and sets the security
headers. Both portals' images currently receive the internal portal's `NEXT_PUBLIC_*`
build args — harmless while the portals share a Clerk instance and an API origin
([`../TODO.md`](../TODO.md), **Deploy — per-portal build args**).

In native dev the root `Makefile` exports the internal portal's `.env.local`, so
`make dev-supplier` unsets those keys before starting the supplier portal; otherwise the
internal values would override the supplier's own file.

## 7. Tests

One Vitest config, three projects: `packages`, `internal-portal`, `supplier-portal`, each
portal aliasing `@/` to its own `src/`. Tests sit beside their subject as `*.test.ts(x)`;
`*.spec.ts` and the `e2e/**` exclude are reserved for Playwright, which does not exist
yet: nothing drives a browser. `QueryProvider`'s error policy is untested too — the
mutator and the status-recovery hook are covered, the provider is not
([`../TODO.md`](../TODO.md), **Web — tests the suite does not have yet**). `make test-web`
runs the suite and the pre-push hook runs it when `web-app/` changed. The traps are in the
`web-app-testing` skill.

## 8. Adding a portal

A third portal is a copy of the supplier portal plus these edits, most of which fail
somewhere other than where they are missing:

| Where | What |
|---|---|
| `web-app/apps/<portal>/` | copy `supplier-portal`; rename in `package.json`; change the role guard in `proxy.ts` and the copy in `unauthorized/page.tsx` |
| `packages/auth/src/permissions.ts` | the role predicate the new `proxy.ts` uses, if no existing one fits |
| `web-app/package.json` | a `dev:<portal>` script |
| `web-app/vitest.config.mts` | a `portal("<portal>")` project |
| `web-app/Dockerfile` | the app's `package.json` in the deps stage |
| `docker-compose.dev.yml`, `docker-compose.prod.yml` | a service with `APP_NAME`; a host port in dev; Traefik labels and a `<PORTAL>_DOMAIN` in prod |
| `Makefile`, `.env.example` | `<PORTAL>_HOST_PORT`, a `dev-<portal>` target, the port in `dev-preflight` and `dev-kill` |
| `scripts/worktree/init.sh`, `clean.sh` | the new port's slot offset and cleanup |
| `scripts/deploy-check.sh` | the domain default and the image assertion |
| `.vscode/tasks.json`, `.vscode/settings.json` | a `Dev:` task; the app in ESLint's working directories |
| `server/.env.<env>` | the origin in `ALLOWED_ORIGINS` |
| Clerk dashboard | the origin, and any new role (`docs/setup/clerk.md`) |

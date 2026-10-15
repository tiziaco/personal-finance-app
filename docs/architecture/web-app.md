# Web app — the app, the packages, and the session

How `web-app/` is put together: one Next.js app over six packages, where
access is decided, and how a request reaches the API. This
describes the system as it stands and is kept current. The working rules — which
package a component goes in, import shapes, the failure modes with no safety net — are
in [`web-app/CLAUDE.md`](../../web-app/CLAUDE.md) and the `web-app-patterns` skill, and
are not repeated here.

---

## 1. Shape

One application and six packages in one pnpm workspace:

```
web-app/
├── apps/
│   └── web/                # the app (@app/web)
└── packages/
    ├── core/               # @app/core        — no renderer: cn(), NavItem, copy, env flags
    ├── ui/                 # @app/ui          — shadcn/Base UI primitives, web only
    ├── components/         # @app/components  — composed chrome: sidebar, user panel, settings
    ├── data-table/         # @app/data-table  — the two tables, filters, URL list state (nuqs)
    ├── auth/               # @app/auth        — AppUser, AuthProvider, useAppAuth
    └── api-client/         # @app/api-client  — generated hooks, types and Zod, plus the mutator
```

**The app is a thin shell** — route groups, a nav list, a user panel, settings tabs —
and everything reusable lives in a package.

**The packages are cut by render dependency:** `core` has none, `ui` is web-only
primitives, `components` is composed chrome built from them. `auth`, `api-client` and
`data-table` are cut by concern.

**The packages import downward only:**

```
apps/web  →  components  →  ui  →  core
apps/web  →  data-table  →  components, ui, core
apps/web  →  api-client  →  auth, core
apps/web  →  auth
```

`components` depends on `core`, `ui` and `lucide-react` and nothing else; what needs
Clerk or the API reaches it through a slot (`userSlot`, `settingsSlot`, `footerSlot`).
`api-client` depends on `auth` for the token and on `core` for copy. `data-table` owns
TanStack Table and nuqs, so the app reaches both only through it; it does not fetch — a
table's rows come from the app's generated hook. It reuses `components`' date picker in its date
filter, so filters and forms pick dates the same way. Only two of these
rules are mechanical: `core` compiles without the `dom` lib, so a `window` in it is a
type error, and each package's `package.json` is the only list of what it may import.
The rest is review — the `web-app-patterns` skill's `references/components.md` lists
the edits that fail far from their cause.

## 2. The app

```
apps/web/src/
├── proxy.ts                         # the access gate (§3)
├── app/
│   ├── layout.tsx                   # ClerkProvider › AuthProvider › ThemeProvider, Toaster
│   ├── (auth)/sign-in/…             # public
│   ├── (auth)/sign-up/…             # public
│   └── (dashboard)/                 # the signed-in shell
│       ├── layout.tsx               # QueryProvider › UrlStateAdapter › SidebarProvider › AppSidebar
│       └── home/
├── components/                      # ClerkUserPanel, GeneralSettings, ServerHealthIndicator
└── lib/hub-nav.ts                   # the sidebar's NavItem list
```

The root layout holds what every route needs, signed in or not. The route group's
layout holds the shell and the query cache — which is the point of §4. The pages under
the shell are placeholders: finance screens are not built yet.

The files in `components/` are the app's own: `ClerkUserPanel` is bound to the app's
auth, `GeneralSettings` and `ServerHealthIndicator` are its settings content; the
`web-app-patterns` skill's `references/components.md` has the rule.

## 3. Who gets in

`src/proxy.ts` — Next 16's name for middleware — runs before every non-static request:

1. `/` redirects to `/home` here, not in a page: a page-level `redirect()` deadlocks the
   App Router during the navigation that follows Clerk's `setActive()`.
2. `/sign-in` and `/sign-up` pass — sign-up is public.
3. `auth.protect()` sends anyone without a session to sign-in.

There are no roles and no organisations, so a session is all it takes.

This gate decides which screens render. It is not what protects data: the API
authorizes every request on its own, from the token (`docs/architecture/authorization.md`).
A route that renders can trust that a session exists and never re-checks it.

## 4. The session boundary

`@app/auth` is the only place the web app reads Clerk's session, and it exposes no
Clerk type. `useAppAuth()` returns:

| Field | What it is |
|---|---|
| `user` | `AppUser` — `name`, `email`, `imageUrl`, each `null` when absent — or `null` while loading or signed out |
| `isLoaded` | Clerk has resolved |
| `isSignedIn` | Clerk has an active session; straight after sign-in it trails the navigation |
| `getToken` | the session token, fresh on every call; `{ forceRefresh }` skips Clerk's cache. Without a session it waits up to 5 s for one being activated, and answers `null` only once the state has settled; a `forceRefresh` does not wait (it follows a refusal, and the first call already waited) |
| `signOut` | ends the session, then loads `signOutUrl` as a new document; a second call while one is in flight shares it |

Two decisions keep one user's data from reaching the next person at the same browser:

- **`QueryProvider` lives in the signed-in route group's layout, not the root.** Leaving
  the group unmounts the provider and drops the cache with it.
- **`signOut()` always ends with `window.location.assign(signOutUrl)`, in a `finally`.**
  A client-side navigation keeps React state, module state and anything a component
  cached; a new document keeps none of it. The `finally` means a failed `endSession`
  still leaves the page.

`useClerk()` is used only to open Clerk's own profile modal. Anything
else from Clerk goes through `@app/auth`, so a change of provider touches one package.

## 5. Talking to the API

The browser calls the API directly, cross-origin — there is no Next.js proxy hop. So
the web origin must be in the server's `ALLOWED_ORIGINS`
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
  hand-written payload type is a bug (the chat stream below is the one exception). The pipeline and its traps are in
  [`api-client-codegen.md`](../guides/api-client-codegen.md).
- **`useApiFetch` is a hook, not a module-level client.** It reads the token on every
  call, so no request can carry another session's token, and it needs no provider. The
  cost: generated hooks run only in client components. A Server Component or route
  handler that needs the API writes its own `fetch`.
- **Every failure is an `ApiError`** — `status`, `body`, `requestId`. The message never
  carries server text.
- **`QueryProvider` owns the error policy.** A query toasts only if it has never
  resolved, so a failing background refetch behind visible data stays quiet. A
  mutation toasts: the user just acted. `meta.silentError` opts either out — `true`
  for every error, or a predicate for the errors the caller shows another way;
  `query-meta.ts` types it for every hook through TanStack's `Register`. The toast
  maps `status` to copy in `@app/core`'s `constants/messages.ts`; server text never
  reaches the UI. `QueryProvider` does not retry a 4xx (the transport's own 401 handling is below).
- **A 401 is an auth event, not an error.** `useApiRequest`, under every hook and the
  chat stream, retries a 401 once with a token fetched fresh (Clerk's cache skipped). A
  second 401 means the session is over: `signOut()` ends it and loads `/sign-in`, so a
  stale session never bounces back from the sign-in page. It only works because the
  server keeps 401 for bad credentials ([`server.md`](./server.md), the error table).
- **Reading an error body goes through the generated Zod schema.** `useServerStatus` is
  the example: `/ready` answers 503 with a valid payload when degraded, which arrives as
  `ApiError.body`. The hook parses it with `GetReadinessResponse` and prefers it over
  the stale `data` the cache still holds.

### The chat screen

- **assistant-ui's `ExternalStoreRuntime`.** TanStack Query (the generated hooks) holds
  conversations and history; the runtime only renders them plus the in-flight exchange. It
  opens that exchange before its first await, so a send cannot be doubled while the
  conversation is created. The exchange is a pure reducer over one immutable `Send` per
  send (`lib/chat/exchange.ts`); the provider's cache edits are `lib/chat/chat-cache.ts`.
- **The stream is the one hand-written call** (`apps/web/src/lib/chat/stream-chat.ts`),
  because orval excludes `streaming` routes. It goes through `useApiRequest`, the
  transport under `useApiFetch`, so its URL, token and `ApiError` are the generated
  hooks' own; it reads the body itself.
- **The route sizes itself to the viewport** inside the shared dashboard container.
  Nothing outside `/chat` changes.
- **Errors.** The history query's `meta.silentError` is `isConversationNotFound`: the
  conversation page renders a 404 (or the 422 of a malformed id) as "This conversation
  doesn't exist", and every other error toasts by `QueryProvider`'s rule.

## 6. Configuration and build

The app reads `apps/web/.env.local`. `NEXT_PUBLIC_*` values are inlined
at build time, so an image is built for one API URL and one Clerk instance.

One `web-app/Dockerfile` builds the app, selected by the `APP_NAME` build arg (`web`), as
a standalone Next.js server listening on 3000. `next.config.ts` lists every workspace
package in `transpilePackages` — they ship raw TypeScript — and sets the security
headers.

In native dev the root `Makefile` exports `apps/web/.env.local`, so
`make dev-web` and the compose build see the same Clerk keys.

## 7. Tests

One Vitest config, two projects: `packages` and `web`, the latter aliasing `@/` to
`apps/web/src/`. Tests sit beside their subject as `*.test.ts(x)`;
`*.spec.ts` and the `e2e/**` exclude are reserved for Playwright, which does not exist
yet: nothing drives a browser. `QueryProvider`'s retry rule and quiet refetch are untested too
([`../TODO.md`](../TODO.md), **Web — tests the suite does not have yet**). `make test-web`
runs the suite and the pre-push hook runs it when `web-app/` changed. The traps are in the
`web-app-testing` skill.

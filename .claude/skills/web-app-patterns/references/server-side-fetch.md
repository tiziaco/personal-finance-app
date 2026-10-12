# Hand-written server fetch

For Server Components, route handlers, `proxy.ts` and node scripts — anywhere no React context
exists, so `useApiFetch` and every generated hook are unavailable.

**Nothing in the repo does this yet**, so the first one written sets the precedent. Follow this shape.

## What you are taking on

The generated client gave you four things for free. On this path you own all four:

| | Generated hook | Here |
|---|---|---|
| Auth | live Clerk token via `useAppAuth()` | you call `auth()` and set the header |
| Types | from the committed contract | **still from the contract** — see below |
| Errors | always `ApiError` | you throw it yourself |
| Error copy | `QueryProvider` toasts curated copy | no provider — you handle it |

Only the auth and error plumbing is genuinely yours to write. **Types are not.** Importing from
`@app/api-client/types` still applies — a hand-written request or response type is a bug on this path
too.

## The base URL trap

`NEXT_PUBLIC_API_URL` is the **browser's** view of the API. In dev it is `http://localhost:8100` in
the main checkout (`apps/web/.env.example`, and `docker-compose.dev.yml`'s build args) — the port
Compose publishes to the host. A git worktree shifts it by its slot.

Server-side code running **inside the web container** resolves `localhost:8100` to that container
itself, not to the API. The request fails with a connection error that looks nothing like a config
problem.

Container-internal traffic must address the service by its Compose name (`http://server:8000`). If a
server-side call needs to work under `make docker-run`, it needs its own variable — an unprefixed
`API_INTERNAL_URL`, not the `NEXT_PUBLIC_` one — and a matching entry for the `web` service in
`docker-compose.dev.yml` and `docker-compose.prod.yml`.

This does not bite on the native path (`Dev: All`), where the API really is on `localhost`. That
asymmetry is what makes it easy to ship broken.

## Shape

Put the helper next to the route that uses it — `apps/web/src/app/(dashboard)/<route>/data.ts`. Do **not** start `src/lib/api/`; `web-app/CLAUDE.md`
forbids that directory, because it becomes a second, hand-maintained API layer competing with the
generated one.

```ts
// apps/web/src/app/(dashboard)/<route>/data.ts
import "server-only"

import { auth } from "@clerk/nextjs/server"
import { ApiError } from "@app/api-client"
import type { SomeResponse } from "@app/api-client/types"

function baseUrl(): string {
  // See "The base URL trap" above before reusing NEXT_PUBLIC_API_URL here.
  const url = process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL
  if (!url) throw new Error("API base URL is not set")
  return url.replace(/\/+$/, "")
}

export async function getSomething(): Promise<SomeResponse> {
  const { getToken } = await auth()
  const token = await getToken()

  const response = await fetch(`${baseUrl()}/api/v1/something`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    // Per-user: never cached. See "Caching" below.
    cache: "no-store",
  })

  if (!response.ok) {
    // Mirror useApiFetch: never response.statusText — the reason phrase is
    // server-supplied text. status, body and requestId carry enough to debug.
    throw new ApiError(
      `HTTP ${response.status}`,
      response.status,
      await response.json().catch(() => null),
      response.headers.get("x-request-id"),
    )
  }

  return (await response.json()) as SomeResponse
}
```

`import "server-only"` is the guard that matters: it turns an accidental client import into a build
error rather than a leaked token at runtime. Next handles the import itself; the package need not be
installed.

## Errors have no toast here

`QueryProvider` is a client provider. Nothing on this path catches the throw, so an `ApiError` from a
Server Component becomes the nearest `error.tsx` boundary.

That boundary must obey the same rule as the toasts: map `error.status` to copy in
`@app/core/constants/messages`. It must never render `error.message` or `error.body` — server
payloads may carry stack traces or internal route names.

If you add an `error.tsx` for this, keep its mapping consistent with `toastForError` in
`packages/api-client/src/query-provider.tsx`. Two mappings that drift are worse than one.

## Caching

The app runs Next 16's earlier caching model — `next.config.ts` does not set `cacheComponents` —
so a `fetch` is not cached unless it asks to be.

Caching is the one real advantage of the server path: `next: { revalidate, tags }` puts the response
in the App Router's data cache, which TanStack Query cannot — it is shared across users and survives
navigation. Pair it with `revalidateTag("<tag>")` in whatever mutates the same resource; a
`revalidate` with no invalidation path is a cache you cannot correct.

**That sharing is also why a per-user response must never be cached.** The cache is keyed by URL, not
by token, so one user's data would be served to the next. Cache only a response that is identical
for every caller, and send that request **without** an `Authorization` header. If the route needs a
token, the data is per-user: `cache: "no-store"`, as above, or the client path.

If a fork turns on `cacheComponents`, caching moves to the `"use cache"` directive and this section
needs rewriting against `node_modules/next/dist/docs/`.

# Data Access

Generic Next.js guidance says "Server Components first, add client fetching only when you need
interactivity." **That default is inverted in this workspace**, and not by preference.

`useApiFetch` (`packages/api-client/src/use-api-fetch.ts`) — the mutator every orval-generated
endpoint routes through — is a React hook, deliberately. A module-scope client would be shared across
concurrent requests in a Next.js server process, so one user's token could serve another user's
request, and it would freeze the first render's `getToken` closure.

The consequence: **every generated hook is client-only.** A Server Component that wants data must
leave the generated client behind and hand-write a fetch — which also means hand-forwarding the Clerk
token and losing the central error→toast mapping in `QueryProvider`.

So the question is never "Server or Client?" in the abstract. It is: **is this data worth giving up
the generated client for?**

## Decision

Start at the top. Take the first row that matches.

| The data is… | Use | Cost |
|---|---|---|
| Anything reachable by a generated hook, rendered in the browser | **Generated hook** — `useGetX()` from `@app/api-client/endpoints/<tag>` | `"use client"` on that component |
| A mutation (create/update/delete) | **Generated mutation hook** | same |
| Polling, filters, search, infinite scroll, optimistic updates | **Generated hook** + TanStack Query options | same |
| From a route carrying the `streaming` tag | **Plain `fetch`** — streaming routes are excluded from generation, so no hook exists | manual auth + errors |
| Needed before first paint, above the fold, and measurably hurt by a client round-trip | **Hand-written server fetch** — see `server-side-fetch.md` | you own auth, types and errors |
| Needed in a route handler, `proxy.ts`, or a node script | **Hand-written server fetch** — no React context exists there | same |

**The default is the first row.** Reach past it only with a reason you could write down. "Server
Components are the modern default" is not one — in this repo it is a downgrade.

### Why the client path is not a compromise here

The generated hook gives you four things the server path makes you rebuild:

1. **Auth.** `useApiFetch` reads the live Clerk token on every call via `useAppAuth()`.
2. **Types.** Request and response types come from the committed OpenAPI contract. A hand-written
   type describing an API payload is a bug.
3. **Errors.** Every hook's `error` is an `ApiError` — `{ status, body, requestId }`.
4. **Error copy.** `QueryProvider` (`packages/api-client/src/query-provider.tsx`) maps `error.status`
   to curated copy in `@app/core/constants/messages` and toasts it centrally. Server-authored text
   never reaches the UI.

Point 4 is a security boundary, not a convenience. See `toastForError` in `query-provider.tsx`.

## Using a generated hook

```tsx
"use client"

import { useGetReadiness } from "@app/api-client/endpoints/system"
import { Skeleton } from "@app/ui/skeleton"

export function ServerStatus() {
  const { data, isPending } = useGetReadiness()

  if (isPending) return <Skeleton className="h-4 w-24" />
  return <span>{data?.status}</span>
}
```

Rules:

- Import **per tag** (`/endpoints/system`), never from a barrel. The tag is the route's FastAPI tag.
- Do not write a `try/catch` to toast. `QueryProvider` already did. Only handle `error` locally when
  this component needs a *different* outcome than the toast — inline empty state, a retry affordance.
- Never render `error.message` or `error.body`. Map `error.status` to `@app/core/constants/messages`.
- Never return `null` while loading. Return a skeleton.
- A background refetch that fails does **not** toast if the query already has data — that is
  intentional. A polling query that should never toast sets `meta: { silentError: true }`; one
  that shows some errors itself passes a predicate, `meta: { silentError: (e) => ... }`, and
  every other error still toasts (`useChatHistory` silences only not-found).
- `QueryProvider` lives in the signed-in route group's layout (`(dashboard)`), never the
  root: the cache must not outlive the session. A generated hook outside that group has no client.

## Shaping the fetch — patterns that hold on either path

- **Fetch once, high up, and pass the data down.** A leaf that calls the same hook as its parent is
  deduplicated by TanStack Query, but the tree now has two owners of one piece of state. Fetch where
  the data's owner is, pass props to the leaves.
- **Filters keep the previous page on screen.** Set `placeholderData: keepPreviousData` on a query
  whose key includes the filters, so changing a filter does not flash an empty table.
- **A list's filters, search, sort and page live in the URL** when the list is the page's main
  content, so a reload or a shared link reproduces it and Back works. Never hand-roll it with
  `useSearchParams` and `router.replace`: the state hook in `url-state.md` owns the URL and feeds the
  generated hook its parameters. A table in a dialog keeps its state local (`data-tables.md`).
- **Static and live parts of one page** can split: the static part as props from above, the live part
  a client component with its own query under `<Suspense fallback={<Skeleton />}>`. The static part is
  only worth a server fetch if it passes the decision table on its own.

## Error handling, wherever the data came from

One rule holds on both paths: **the server's words never reach the user.** Status codes map to copy
you wrote.

```tsx
// ✅ a status maps to copy we control
if (error.status === 404) toast.error(messages.toasts.notFound)

// ❌ server-authored text — may carry stack traces or internal route names
toast.error(error.message)
toast.error(String(error.body))
```

## Never

- **Never create `apps/*/src/lib/api/`.** The generated client is that layer. If you are reaching
  for it, you are either on the server path (use `server-side-fetch.md`, which puts the
  helper next to its route) or you are about to hand-write something orval already generated.
- **Never hand-edit `packages/api-client/src/generated/`.** orval runs with `clean: true`.
- **Never change a server route without `make gen-contract` in the same commit.** The pre-commit hook
  blocks it; the image build and CI fail on it.
- **Never call a generated hook outside a Client Component.** It calls `useAppAuth()` and will throw.

## Reference

| File | Read when |
|---|---|
| `server-side-fetch.md` | You took a server row in the decision table, or need a route handler / `proxy.ts` / script to call the API |
| [`docs/guides/api-client-codegen.md`](../../../../docs/guides/api-client-codegen.md) | You are changing the pipeline itself — orval config, the mutator, the post-processing script |

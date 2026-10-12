---
name: web-app-patterns
description: >
  Coding patterns and conventions for the Next.js workspace (web-app/). Use whenever wiring a page or
  component to the API, choosing between a Server Component and a client hook, building a table or a
  list with filters, search, sort or pagination, polling or streaming, handling an API error, creating
  a component or deciding which package it belongs in, adding a shadcn primitive or a workspace
  package, adding a page or a sidebar entry, a loading state, reading the signed-in user, or signing out. Trigger on tasks like "fetch X on this page", "call the /api/v1/... endpoint",
  "add a mutation", "poll for status", "add a table of X", "add a filter", "keep the filters in the
  URL", "add a component", "add a screen for X", or any work
  touching apps/web/src/, proxy.ts or packages/. Use this instead of generic Next.js, React, TanStack
  Table or Clerk advice — the generic defaults are wrong here.
---

# Web App Patterns

`web-app/` is one Next.js 16 app, `apps/web/`, over six shared packages. The architecture — the package stack, the
access gate, the session boundary, the path to the API — is in `docs/architecture/web-app.md`, and this
skill does not restate it. This skill covers how the code inside that structure is written. Read the
relevant reference file before writing any code. Tests are the `web-app-testing` skill.

Next.js 16 APIs differ from training data: before writing Next-specific code, read the relevant guide in
`web-app/apps/web/node_modules/next/dist/docs/`.

## Reference files

| Topic | File | Read when… |
|---|---|---|
| Data access | `references/data-access.md` | Wiring anything to the API — hook or server fetch, mutations, pagination, filters, polling, streaming, errors. **Read before choosing a Server Component for data** |
| Data tables | `references/data-tables.md` | Any table — client or server-paginated, its columns and sorting, a table in a dialog or drawer, column visibility |
| URL list state | `references/url-state.md` | A page's main list: filters, search, sort and page in the URL, filter chips, a date filter, two lists on one page, Back/Forward out of sync. **Read `data-tables.md` first** |
| Server-side fetch | `references/server-side-fetch.md` | The decision table sent you to a server fetch, or a route handler / `proxy.ts` / script calls the API |
| Components, primitives, packages | `references/components.md` | Creating any component — which of six homes it goes in — using Base UI, adding a shadcn primitive, or adding a workspace package |
| Auth | `references/auth.md` | Reading the user, signing out, or touching `proxy.ts` |
| Adding a screen | `references/pages.md` | A new route — its route group, sidebar entry, loading state, copy — or a redirect |

## Quick rules (always apply)

- Every generated hook is client-only: `useApiFetch` is a hook. For data, the "Server Components first"
  default is inverted — the page stays a Server Component, the part that renders server data is a client
  component calling a generated hook
- Every request and response type comes from `@app/api-client`; a hand-written payload type is a bug.
  Never hand-edit `packages/api-client/src/generated/`, and run `make gen-contract` in the same commit as
  the server route change
- Hooks are imported per tag, `@app/api-client/endpoints/<tag>`; there is no `apps/*/src/lib/api/` layer
- Never render `error.message` or `error.body`. `QueryProvider` already toasts copy mapped from
  `error.status`; handle `error` locally only for a different outcome (an inline empty state, a retry)
- Loading states return a skeleton, never `null`
- A table is `ClientDataTable` or `ServerDataTable` from `@app/data-table`; list state lives in its
  state hook — never a `useState` copy of filters, search, page or sort
- Base UI, not Radix: the `render` prop, never `asChild`
- `@app/ui` is imported by subpath (`@app/ui/button`); `@app/components` and `@app/core` have no barrel
- Client components read the user through `useAppAuth()` from `@app/auth` — never Clerk's `useUser()` /
  `useAuth()` — and sign out with its `signOut()`
- `QueryProvider` sits in the signed-in route group's layout, never the root: the cache must not outlive
  the session
- `"use client"` only where a component needs hooks, handlers or browser APIs; files are kebab-case
- A component with a branch — a state, a mapping — gets a co-located `*.test.tsx`. Load the
  `web-app-testing` skill before writing it

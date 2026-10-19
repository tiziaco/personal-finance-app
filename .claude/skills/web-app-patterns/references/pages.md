# Adding a Screen

A new route: where the file goes, its sidebar entry, its loading state and its copy. The
shell it renders inside is `docs/architecture/web-app.md` §2; the data it shows is `data-access.md`.
Paths below are relative to `web-app/apps/web/src/`.

The existing page (`home/`) is a placeholder — they are where a fork's domain
starts, not examples of finished screens.

## Where the route goes

Inside the signed-in route group, `app/(dashboard)/`. Outside it there is no sidebar and no `QueryProvider`, so
a generated hook has no client. Only `(auth)/` — sign-in and sign-up — lives outside.

```tsx
// app/(dashboard)/transactions/page.tsx — a Server Component
import { TransactionList } from "@/components/transactions/transaction-list"

function TransactionsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Transactions</h1>
      <TransactionList />
    </div>
  )
}

export default TransactionsPage
```

The page stays a Server Component. The part that renders server data is a `"use client"` component in
`components/<area>/` calling a generated hook — `data-access.md` has the decision table.

No auth check in the page: `proxy.ts` already sent anyone without a session to sign-in (`auth.md`).

## The sidebar entry

`lib/hub-nav.ts` holds the app's `HUB_NAV: NavItem[]` (`NavItem` is `@app/core/types/nav`):

```ts
{ title: "Transactions", url: "/transactions", icon: ArrowLeftRight },
```

- `title` is the display label; `icon` a `lucide-react` component.
- The sidebar is a 104px rail (`w-26`) with the label under the icon: a new entry's `title` must
  fit there unwrapped. There are no sub-entries.
- The active entry is an exact match on `pathname`: `/transactions/123` highlights nothing. A detail page
  under a list page does not light up its parent.

## Loading

Each route group has one `loading.tsx` — a title bar and two blocks of `Skeleton`. It covers every page
in the group; add a `loading.tsx` to a segment only when its layout differs enough that the shared one
jumps.

Inside a component, a loading state returns a skeleton shaped like what it replaces — never `null`:

- `Skeleton` from `@app/ui/skeleton` carries `bg-muted`, right for page content.
- Inside the sidebar, override with `bg-sidebar-accent` (`packages/components/src/layout/user-panel.tsx`).
- `isLoaded` from `useAppAuth()` and `isPending` from a query both get a skeleton.

## Copy

- UI labels are English and written inline; there is no i18n library.
- Error copy is never written in a screen: `QueryProvider` toasts from
  `@app/core/constants/messages` (`messages.toasts.*`), mapped from `error.status`. A new message for a
  new status goes there.

## Redirects

`/` → `/home` lives in `proxy.ts`. Never add an `app/page.tsx` that calls `redirect()`: during the
navigation that follows Clerk's `setActive()`, a page-level redirect deadlocks the App Router — a blank
page with the URL stuck on `/`. A redirect that must happen before a page renders goes in `proxy.ts`.

## Verify

- The route is under the signed-in group; `HUB_NAV` has the entry if it is top-level.
- No page or component returns `null` while loading.
- `make dev-web` from the repo root, then open the route from the sidebar.

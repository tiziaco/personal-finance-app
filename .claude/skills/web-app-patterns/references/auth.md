# Auth and Role-Gated UI

Reading the signed-in user, showing UI by role, signing out, and adding a role. Who gets into a portal
is `docs/architecture/web-app.md` §3; how the API authorizes is `docs/architecture/authorization.md`.
Paths below are relative to `web-app/`.

The project is on `@clerk/nextjs` **v6 (Core 2)**. Current Clerk docs describe APIs that do not exist
here — `<Show>` among them — so generic Clerk advice is wrong by default.

## What has already been checked

Every route outside sign-in passes `apps/<portal>/src/proxy.ts` first: `auth.protect()`, then
`auth().orgRole` → `getUserRole()` → the portal's predicate (`isInternalRole` / `isSupplierRole`), and
`/unauthorized` for anyone else. A page that renders has a session and a role that belongs in that
portal — never re-check either.

That gate decides which screens render. It does not protect data: the API authorizes every request
from the token. Hiding a button is presentation; the route behind it enforces the role on its own.

## Reading the user

`useAppAuth()` from `@app/auth` in a client component — never Clerk's `useUser()` or `useAuth()`.
`packages/auth` is the portability seam: only `AuthProvider` touches Clerk's hooks, and the context
exposes no vendor type.

| Field | Is |
|---|---|
| `user` | `AppUser` — `{ name, email, imageUrl }`, each `string \| null`; `null` while loading |
| `role` | `Role \| null` |
| `isLoaded` | `false` until Clerk has initialised — check it before role-dependent UI |
| `getToken` | the bearer token; only `@app/api-client`'s mutator needs it |
| `signOut` | see below |

`useClerk()` is only for opening Clerk's own UI (`openUserProfile`, `openOrganizationProfile`). In a
Server Component, `currentUser()`.

The model to copy is `apps/internal-portal/src/components/layout/clerk-user-panel.tsx`.

## Gating on role

`Role` is a const object — `PROJECT_MANAGER`, `REVIEWER`, `APPROVER`, `SUPPLIER` — and `Role` the
union of its values. Compare with it:

```tsx
"use client"

import { Role, useAppAuth } from "@app/auth"
import { Skeleton } from "@app/ui/skeleton"

export function InviteAction() {
  const { isLoaded, role } = useAppAuth()

  if (!isLoaded) return <Skeleton className="h-8 w-36" />
  if (role !== Role.PROJECT_MANAGER) return null   // hidden, not loading
  return <InviteButton />
}
```

- The declarative form is `<Protect role="org:project_manager">` from `@clerk/nextjs` — Core 2's
  API, and the one that works in a Server Component. It names Clerk's `org:`-prefixed slug and imports
  the vendor directly, so prefer the hook wherever the component is already a client component.
- Never `<Show when={{ role }}>` (not in v6), `has({ role })` in a component, or
  `sessionClaims.metadata.role` (user metadata, not the org role).
- In `proxy.ts`, read `const { orgRole } = await auth()` and pass it through `getUserRole()`.
- Display a role with `ROLE_LABELS[role]`, never the slug.
- A role gate is a branch, so it earns a test: mock `useAppAuth` and cover each role, `null` and
  `isLoaded: false`. `clerk-user-panel.test.tsx` is the model; the `web-app-testing` skill has the rest.

## Signing out

`signOut()` from `useAppAuth()`, never `useClerk().signOut` or a router push. It ends the session,
then loads `AuthProvider`'s `signOutUrl` (`/sign-in` in both root layouts) as a new document, so
nothing the previous user cached survives — no query cache, no context. `QueryProvider` sits in the
route-group layout, not the root, for the same reason.

```tsx
<Button onClick={() => void signOut()}>Sign out</Button>
```

## Adding a role

1. `packages/auth/src/permissions.ts`: the slug in `Role`, its label in `ROLE_LABELS`, and — if no
   predicate fits — a new `is<X>Role`. `permissions.test.ts` is next to it.
2. The predicate in the `proxy.ts` of each portal that admits it.
3. The role in the Clerk dashboard — `docs/setup/clerk.md`.
4. The server's side of it — `docs/architecture/authorization.md`.

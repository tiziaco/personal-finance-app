# Auth

Reading the signed-in user and signing out. Who gets into the app is `docs/architecture/web-app.md` §3; how the
API authorizes is `docs/architecture/authorization.md`. Paths below are relative to `web-app/`.

The project is on `@clerk/nextjs` **v6 (Core 2)**. Current Clerk docs describe APIs that do not exist
here — `<Show>` among them — so generic Clerk advice is wrong by default.

The user is the tenant, with nothing above or beside it, and a session is all it takes.

## What has already been checked

Every route outside `/sign-in` and `/sign-up` passes `apps/web/src/proxy.ts` first: `auth.protect()` sends anyone
without a session to sign-in. Sign-up is public. A page that renders has a session — never re-check it.

That gate decides which screens render. It does not protect data: the API authorizes every request
from the token, and answers 404 for a row that is not the caller's. Hiding a button is presentation.

## Reading the user

`useAppAuth()` from `@app/auth` in a client component — never Clerk's `useUser()` or `useAuth()`.
`packages/auth` is the portability seam: only `AuthProvider` touches Clerk's hooks, and the context
exposes no vendor type.

| Field | Is |
|---|---|
| `user` | `AppUser` — `{ name, email, imageUrl }`, each `string \| null`; `null` while loading |
| `isLoaded` | `false` until Clerk has initialised — render a skeleton until it is true |
| `getToken` | the bearer token; only `@app/api-client`'s mutator needs it |
| `signOut` | see below |

`useClerk()` is only for opening Clerk's own UI (`openUserProfile`). In a Server Component, `currentUser()`.

The model to copy is `apps/web/src/components/layout/clerk-user-panel.tsx`.

## Signing out

`signOut()` from `useAppAuth()`, never `useClerk().signOut` or a router push. It ends the session,
then loads `AuthProvider`'s `signOutUrl` (`/sign-in` in the root layout) as a new document, so
nothing the previous user cached survives — no query cache, no context. `QueryProvider` sits in the
route-group layout, not the root, for the same reason.

```tsx
<Button onClick={() => void signOut()}>Sign out</Button>
```

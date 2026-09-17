# Clerk Auth Fixes Port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the four auth fixes from the B2C fork's PR #1 into this two-portal
repo, and close the `/unauthorized` redirect loop the role guard walks into.

**Architecture:** Four independent defects, no shared state between them. One
lives in the shared `@app/ui` package and is fixed once for both portals; the
other three are duplicated per portal and are fixed twice, identically. The
`/unauthorized` fix is new work, not a port — it exists because both `proxy.ts`
files redirect a wrong-role user to a route neither app defines.

**Tech Stack:** Next.js 16 (App Router), `@clerk/nextjs` v6, Base UI
(`@base-ui/react`), pnpm workspaces, TypeScript.

**Spec:** No spec file — this was brainstormed as a bounded change. The upstream
source is
[`tiziaco/fullstack-b2c-nextjs-fastapi-template` PR #1](https://github.com/tiziaco/fullstack-b2c-nextjs-fastapi-template/pull/1),
merged as `3d58767`. The four upstream commits this plan ports are
`1e7e0da` (env rename), `8e6f792` (middleware redirect + `signOut`), and
`efef2db` (Base UI `render`). The fork's `scripts/clerk/` tooling from the same
PR is **out of scope** and will be planned separately.

## Global Constraints

- **Both portals get every app-level fix.** `internal-portal` and
  `supplier-portal` are separate Next apps with their own copies of
  `page.tsx`, `proxy.ts` and `clerk-user-panel.tsx`. A fix applied to one and
  not the other is a half-fix. Only the `@app/ui` change is shared.
- **User-facing copy is Italian.** See `src/lib/messages.ts` in either app and
  `ROLE_LABELS` in `web-app/packages/auth/src/permissions.ts`. New page copy
  follows suit. Code comments, identifiers and docs stay English.
- **Prettier: no semicolons.** Config at `web-app/.prettierrc`; `.vscode/settings.json`
  formats on save. `make check-web` runs `prettier --check` and will fail on a
  stray semicolon.
- **No frontend test runner exists.** There is no Jest/Vitest/Playwright setup in
  `web-app/`. Verification is `pnpm type-check`, `make check-web`, and named
  browser checks. Do not invent a test harness as part of this plan.
- **`NEXT_PUBLIC_*` is inlined at build time.** Task 2's rename is not observable
  until the portal is rebuilt or the dev server restarted. See
  `docs/setup/clerk.md` for the standing note.
- **Commit trailers:** each commit ends with the repo's usual
  `Co-Authored-By:` attribution line if the session is configured for it.

---

### Task 0: Branch

**Files:** none.

**Interfaces:**
- Consumes: nothing.
- Produces: the working branch every later task commits onto.

- [ ] **Step 1: Confirm the tree is clean**

Run: `git status --porcelain`
Expected: no output. If there is output, stop and ask — this plan assumes a
clean `main`.

- [ ] **Step 2: Create the branch**

```bash
git checkout -b fix/clerk-auth-redirects
```

- [ ] **Step 3: Verify**

Run: `git branch --show-current`
Expected: `fix/clerk-auth-redirects`

---

### Task 1: Base UI `render` in `SidebarMenuButton`

Independent of every other task, and the only one that touches a shared package.
Do it first so the rest of the branch builds on a warning-free console.

**Files:**
- Modify: `web-app/packages/ui/src/components/ui/sidebar.tsx:541`
- Test: none (no frontend test runner — see Global Constraints)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. `SidebarMenuButton`'s public props are unchanged and the
  rendered DOM is unchanged.

**Background.** Base UI calls a function-valued `render` as a plain function
during reconciliation. Passing the bare `TooltipTrigger` *component* therefore
runs `TooltipPrimitive.Trigger`'s hooks inside `SidebarMenuButton`'s own render
pass rather than in a fiber of their own, and Base UI warns about it on every
page load:

```
Base UI: The `render` prop received a function named `TooltipTrigger`... can
break the Rules of Hooks during reconciliation.
```

`web-app/CLAUDE.md` already documents the element form and warns against the
Radix `asChild` pattern, so this line had drifted from the repo's own rule.
Nesting the caller's `render` inside is Base UI's documented composition idiom
and fixes a second, latent bug on the same line: this is the only component in
the package that *overrode* a caller-supplied `render` instead of forwarding it,
so any `render` passed alongside `tooltip` was silently dropped. No caller does
that today.

- [ ] **Step 1: Read the current line in context**

Run: `sed -n '530,550p' web-app/packages/ui/src/components/ui/sidebar.tsx`
Expected: line 541 reads `    render: !tooltip ? render : TooltipTrigger,`

- [ ] **Step 2: Replace the line**

Replace exactly this:

```tsx
    render: !tooltip ? render : TooltipTrigger,
```

with this:

```tsx
    // An element, never the bare component: Base UI calls a function-valued
    // `render` as a plain function during reconciliation, which would run the
    // trigger's hooks outside a fiber. Nesting the caller's own `render` inside
    // is Base UI's composition idiom, and keeps it from being dropped here.
    render: !tooltip ? render : <TooltipTrigger render={render} />,
```

- [ ] **Step 3: Type-check**

Run: `cd web-app && pnpm type-check`
Expected: exit 0, no errors.

- [ ] **Step 4: Lint and format**

Run: `make check-web`
Expected: `PASS`-equivalent — ESLint clean, `prettier --check` clean.

- [ ] **Step 5: Commit**

```bash
git add web-app/packages/ui/src/components/ui/sidebar.tsx
git commit -m "fix(ui): pass an element, not a component, to SidebarMenuButton's render

Base UI calls a function-valued \`render\` as a plain function during
reconciliation, so passing the bare TooltipTrigger component ran the
trigger's hooks inside SidebarMenuButton's own render pass rather than in a
fiber of their own. It warned on every page load.

Nesting the caller's \`render\` inside is Base UI's documented composition
idiom and fixes a second bug on the same line: this was the only component
in the package that overrode a caller-supplied \`render\` instead of
forwarding it, so any \`render\` passed alongside \`tooltip\` was silently
dropped. No caller does that today, so that part is latent.

DOM is unchanged: mergeProps puts the state-derived attributes in its first
argument and tooltip.tsx spreads {...props} after its own literal, so
data-slot stays \"sidebar-menu-button\"."
```

- [ ] **Step 6: Browser check (deferred to Task 5)**

The console check for this fix is bundled into Task 5's walkthrough so the
portals are rebuilt once, not four times. Nothing to do here.

---

### Task 2: Rename the deprecated Clerk redirect variables

**Files:**
- Modify: `web-app/apps/internal-portal/.env.example:15-16`
- Modify: `web-app/apps/supplier-portal/.env.example:15-16`
- Modify: `web-app/apps/internal-portal/.env.local:10-11` (gitignored — edit, do not commit)
- Modify: `web-app/apps/supplier-portal/.env.local:10-11` (gitignored — edit, do not commit)
- Modify: `web-app/apps/internal-portal/README.md:43-44`
- Modify: `web-app/apps/supplier-portal/README.md:43-44`
- Modify: `docs/setup/clerk.md:97-98`
- Test: none

**Interfaces:**
- Consumes: nothing.
- Produces: the env variable names Task 3 depends on. Task 3's `/` → `/home`
  middleware redirect and this rename interact — with the legacy names, a
  sign-in carrying `?redirect_url=` silently drops the configured destination,
  which is exactly the state Task 3's bug report describes. Do Task 2 first.

**Background.** `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` and its sign-up twin map,
via `mergeNextClerkPropsWithEnv`, onto the `afterSignInUrl` / `afterSignUpUrl`
props that `@clerk/nextjs` v6 deprecated. Not cosmetic: when the sign-in page is
reached with a `?redirect_url=` — after a sign-out, or when middleware bounces
someone off a protected route — that value takes priority and the legacy prop is
ignored outright, so the configured destination is silently dropped. This
template hid the symptom because `/` redirected authenticated users to `/home`
anyway, so both paths happened to converge.

`FALLBACK` rather than `FORCE` keeps "send them back where they were heading"
and only falls back to `/home`.

- [ ] **Step 1: Find every occurrence**

Run:
```bash
grep -rn "AFTER_SIGN" --include='*.md' --include='.env*' . \
  | grep -v node_modules | grep -v '/.next/'
grep -n "AFTER_SIGN" web-app/apps/*/.env.local
```
Expected: the 7 locations listed under **Files**. `docs/superpowers/plans/2026-09-03-ws2-deploy-compose-traefik.md`
also matches — that is a historical plan document describing what was true when
it was written. **Leave it alone.**

- [ ] **Step 2: Rewrite both `.env.example` files**

In `web-app/apps/internal-portal/.env.example` and
`web-app/apps/supplier-portal/.env.example`, replace:

```bash
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/home
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/home
```

with:

```bash
# Where to land when nothing else is requested. FALLBACK, not FORCE: a sign-in
# reached with a ?redirect_url= (after sign-out, or bounced off a protected
# route) still honours that destination.
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/home
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/home
```

Note: `supplier-portal` has no sign-up route (`src/app/(auth)/sign-up/` exists
only in `internal-portal`), but its `.env.example` already carries
`NEXT_PUBLIC_CLERK_SIGN_UP_URL`. Keep the two files symmetrical — rename the
sign-up variable there too rather than dropping it.

- [ ] **Step 3: Rewrite both `.env.local` files**

Same two lines, same replacement, in `web-app/apps/internal-portal/.env.local`
and `web-app/apps/supplier-portal/.env.local`. These are gitignored working
files; the rename is what makes the change observable in Task 5.

Run: `grep -n "FALLBACK_REDIRECT" web-app/apps/*/.env.local`
Expected: four lines, two per file.

- [ ] **Step 4: Update both portal READMEs**

In `web-app/apps/internal-portal/README.md` and
`web-app/apps/supplier-portal/README.md`, replace lines 43-44:

```bash
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/home
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/home
```

with:

```bash
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/home
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/home
```

- [ ] **Step 5: Update the setup doc's table**

In `docs/setup/clerk.md`, replace the two table rows at lines 97-98:

```markdown
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` | `/home` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL` | `/home` |
```

with:

```markdown
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/home` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/home` |
```

Then, immediately below the sentence that begins "None of these are read by
application code", add this paragraph:

```markdown
`FALLBACK`, not `FORCE`, and not the older `AFTER_SIGN_IN_URL`: the legacy names
map onto props `@clerk/nextjs` v6 deprecated, and a sign-in reached with a
`?redirect_url=` ignores the legacy prop outright rather than falling back to it.
The fallback form honours the requested destination and only defaults to `/home`
when none was asked for.
```

- [ ] **Step 6: Confirm nothing was missed**

Run:
```bash
grep -rn "AFTER_SIGN" --include='*.md' --include='.env*' . \
  | grep -v node_modules | grep -v '/.next/' | grep -v docs/superpowers/plans
grep -n "AFTER_SIGN" web-app/apps/*/.env.local || echo "clean"
```
Expected: no output from the first command; `clean` from the second.

- [ ] **Step 7: Format check**

Run: `make check-web`
Expected: clean. (`prettier --check` covers the Markdown files.)

- [ ] **Step 8: Commit**

Note `.env.local` is gitignored and will not appear in `git status` — that is
expected, and it is why it is absent from the `git add` below.

```bash
git add web-app/apps/internal-portal/.env.example \
        web-app/apps/supplier-portal/.env.example \
        web-app/apps/internal-portal/README.md \
        web-app/apps/supplier-portal/README.md \
        docs/setup/clerk.md
git commit -m "fix(web): replace Clerk's deprecated after-sign-in redirect variables

NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL and its sign-up twin map, via
mergeNextClerkPropsWithEnv, onto the afterSignInUrl/afterSignUpUrl props that
@clerk/nextjs v6 deprecated. Rename both to the current
*_FALLBACK_REDIRECT_URL names, in both portals.

Not cosmetic. When the sign-in page is reached with a ?redirect_url= --
after a sign-out, or when middleware bounces someone off a protected route
-- that value takes priority and the legacy prop is ignored outright, so the
configured destination is silently dropped. The template hid this because /
redirected authenticated users to /home anyway, so both paths happened to
converge.

FALLBACK rather than FORCE keeps \"send them back where they were heading\"
and only falls back to /home."
```

---

### Task 3: Move the `/` → `/home` redirect into middleware

**Files:**
- Modify: `web-app/apps/internal-portal/src/proxy.ts`
- Modify: `web-app/apps/supplier-portal/src/proxy.ts`
- Delete: `web-app/apps/internal-portal/src/app/page.tsx`
- Delete: `web-app/apps/supplier-portal/src/app/page.tsx`
- Modify: `web-app/apps/internal-portal/src/components/layout/clerk-user-panel.tsx`
- Modify: `web-app/apps/supplier-portal/src/components/layout/clerk-user-panel.tsx`
- Test: none

**Interfaces:**
- Consumes: Task 2's renamed env variables (the fallback only behaves as
  described once the non-deprecated names are in place).
- Produces: the `if (req.nextUrl.pathname === "/")` block at the top of both
  `clerkMiddleware` callbacks. Task 4 inserts its own early return into the same
  two functions, *after* `auth.protect()` — the two blocks do not overlap, but
  Task 4's implementer needs to know this one is already there.

**Background.** Signing in could leave the browser on a blank page at `/`,
recoverable only by a manual reload.

The chain: `signOut()` with no arguments navigates to `/`, which `auth.protect()`
bounces to `/sign-in?redirect_url=http://localhost:3000/`. That `redirect_url`
outranks the sign-in fallback (Task 2), so Clerk `router.push()`es to `/` after
`setActive()`. `app/page.tsx` was nothing but `redirect("/home")`, and on an RSC
navigation that arrives inside the flight stream as a rejected promise —
`5:E{"digest":"NEXT_REDIRECT;replace;/home;307;"}` — rather than as an HTTP
redirect. The router follows it, fetches `/home?_rsc=` twice (both 200, a
complete payload) and then never commits: `document.body` is empty while
`location.href` stays `/`.

It is the destination, not `redirect()` in general, that is at fault:
`router.push('/')` from `/home` while signed in soft-navigates, bounces through
the same `redirect()` and renders fine. It only deadlocks in the transition
following `setActive()`, moving from the `(auth)` catch-all into the dashboard
layout.

A middleware redirect is a real 307 resolved before the RSC layer, so it cannot
reach the router in that state. Placing it **before** `auth.protect()` also keeps
`/` out of the `?redirect_url=` a bounced visitor carries into sign-in: that is
now `.../home`, so no path can regenerate the poisoned value.

`signOut({ redirectUrl: "/sign-in" })` then saves the two hops through `/`.

- [ ] **Step 1: Confirm the middleware matcher covers `/`**

Run: `sed -n '/export const config/,/^}/p' web-app/apps/internal-portal/src/proxy.ts`
Expected: the matcher is
`"/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|...)).*)"`. The capture group's `.*`
matches the empty string and the negative lookahead passes, so `/` is matched.
If this is ever narrowed, deleting `page.tsx` would turn `/` into a 404.

- [ ] **Step 2: Add the redirect to `internal-portal/src/proxy.ts`**

Insert immediately after the `export default clerkMiddleware(async (auth, req) => {`
line, before the existing `// Allow public routes` comment:

```ts
  // `/` is an alias for `/home`, and the redirect has to happen here rather
  // than in an `app/page.tsx` calling redirect(). A page-level redirect reaches
  // a client-side navigation as a flight-stream error, not an HTTP redirect,
  // and the App Router deadlocks on one during the transition that follows
  // Clerk's setActive() — blank page, URL stuck on `/`, recoverable only by a
  // manual reload. Redirecting before auth.protect() also keeps `/` out of the
  // ?redirect_url= that a bounced visitor carries into sign-in, so they come
  // back to `/home` directly instead of through `/`.
  if (req.nextUrl.pathname === "/") {
    return NextResponse.redirect(new URL("/home", req.url))
  }

```

`NextResponse` is already imported in both files (the role guard uses it), so no
import change is needed. Verify with
`grep -n "NextResponse" web-app/apps/internal-portal/src/proxy.ts`.

- [ ] **Step 3: Add the same block to `supplier-portal/src/proxy.ts`**

Identical insertion, identical position. The two files differ only in their role
guard (`isInternalRole` vs `isSupplierRole`); this block is byte-identical in
both.

- [ ] **Step 4: Delete both root pages**

```bash
git rm web-app/apps/internal-portal/src/app/page.tsx \
       web-app/apps/supplier-portal/src/app/page.tsx
```

- [ ] **Step 5: Redirect sign-out straight to `/sign-in`**

In **both** `src/components/layout/clerk-user-panel.tsx` files (they are
byte-identical), replace:

```tsx
      onSignOut={() => signOut()}
```

with:

```tsx
      // Sign out straight to /sign-in. The default lands on `/`, which
      // middleware then bounces twice to reach the same place.
      onSignOut={() => signOut({ redirectUrl: "/sign-in" })}
```

- [ ] **Step 6: Type-check**

Run: `cd web-app && pnpm type-check`
Expected: exit 0. A dangling import of the deleted `page.tsx` would surface
here; there should be none — nothing imports a route file.

- [ ] **Step 7: Lint and format**

Run: `make check-web`
Expected: clean.

- [ ] **Step 8: Verify the redirect against a running dev server**

Start the internal portal (`cd web-app && pnpm dev:internal`), then, signed out:

Run: `curl -sI http://localhost:3000/ | head -3`
Expected: `HTTP/1.1 307 Temporary Redirect` with `location: /home`.

Run: `curl -sI http://localhost:3000/home | head -5`
Expected: a 307 to `/sign-in?redirect_url=` whose value ends in `%2Fhome` —
**not** `%2F`. That is the whole point of redirecting before `auth.protect()`.

Repeat both against `http://localhost:3002` for the supplier portal. Stop the
dev servers afterwards.

- [ ] **Step 9: Commit**

```bash
git add web-app/apps/internal-portal/src/proxy.ts \
        web-app/apps/supplier-portal/src/proxy.ts \
        web-app/apps/internal-portal/src/components/layout/clerk-user-panel.tsx \
        web-app/apps/supplier-portal/src/components/layout/clerk-user-panel.tsx
git commit -m "fix(web): redirect / to /home in middleware, not in a page

Signing in could leave the browser on a blank page at /, recoverable only by
a manual reload.

The chain: signOut() with no arguments navigates to /, which auth.protect()
bounces to /sign-in?redirect_url=http://localhost:3000/. That redirect_url
outranks the sign-in fallback, so Clerk router.push()es to / after
setActive(). app/page.tsx was nothing but redirect(\"/home\"), and on an RSC
navigation that arrives inside the flight stream as a rejected promise --
5:E{\"digest\":\"NEXT_REDIRECT;replace;/home;307;\"} -- rather than as an HTTP
redirect. The router follows it, fetches /home?_rsc= twice, and never
commits: document.body is empty while location.href stays /.

A middleware redirect is a real 307 resolved before the RSC layer, so it
cannot reach the router in that state. Placing it before auth.protect() also
keeps / out of the ?redirect_url= a bounced visitor carries into sign-in:
that is now .../home, so no path can regenerate the poisoned value.

signOut({ redirectUrl: \"/sign-in\" }) then saves the two hops through /.

Applied to both portals; the two proxy.ts files differ only in their role
guard."
```

---

### Task 4: Give `/unauthorized` a route and break the redirect loop

Not a port — this defect is specific to this repo, which has a role guard the
B2C fork does not.

**Files:**
- Create: `web-app/apps/internal-portal/src/app/unauthorized/page.tsx`
- Create: `web-app/apps/supplier-portal/src/app/unauthorized/page.tsx`
- Modify: `web-app/apps/internal-portal/src/proxy.ts`
- Modify: `web-app/apps/supplier-portal/src/proxy.ts`
- Test: none

**Interfaces:**
- Consumes: Task 3's `/` → `/home` block, already at the top of both middleware
  callbacks. This task inserts a *second* early return, in a different position.
- Produces: nothing other tasks depend on.

**Background.** Both `proxy.ts` files end with:

```ts
  if (!role || !isInternalRole(role)) {
    return NextResponse.redirect(new URL("/unauthorized", req.url))
  }
```

Neither app defines that route. Worse than a 404: `/unauthorized` matches the
middleware matcher, is not in `isPublicRoute`, and passes `auth.protect()` (the
user *is* signed in — they just have the wrong role), so it reaches the same role
check, fails it again, and redirects to itself. The browser gives up with
`ERR_TOO_MANY_REDIRECTS`. A supplier who opens the internal portal sees a browser
error page, not a message.

**Where the early return goes, and why not `isPublicRoute`.** Adding
`/unauthorized` to `isPublicRoute` would also skip `auth.protect()`, exposing the
page to signed-out visitors and widening a matcher whose name means "sign-in and
sign-up". Instead the check goes *after* `auth.protect()` and *before* the role
check: you must be signed in to see it, and the loop is broken exactly where it
forms.

**Not the Next.js `unauthorized.tsx` convention.** Next 16 ships a reserved
`app/unauthorized.tsx` file paired with the `unauthorized()` function behind the
`authInterrupts` flag. That is a different mechanism — it renders in place
without changing the URL. The middleware here issues a real redirect to a real
URL, so what is needed is an ordinary route segment,
`app/unauthorized/page.tsx`. The two do not collide.

- [ ] **Step 1: Create the internal portal's page**

Create `web-app/apps/internal-portal/src/app/unauthorized/page.tsx`:

```tsx
"use client"

import { useClerk } from "@clerk/nextjs"
import { Button } from "@app/ui/button"

export default function UnauthorizedPage() {
  const { signOut } = useClerk()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-2xl font-semibold">Accesso non consentito</h1>
      <p className="text-muted-foreground max-w-md">
        Il tuo account non ha i permessi per accedere al portale interno.
        Contatta un amministratore se ritieni che si tratti di un errore.
      </p>
      <Button onClick={() => signOut({ redirectUrl: "/sign-in" })}>
        Esci
      </Button>
    </div>
  )
}
```

The page sits outside the `(dashboard)` route group on purpose: it gets the root
`app/layout.tsx` only, with no sidebar. A user who cannot enter the portal should
not be shown its chrome.

- [ ] **Step 2: Create the supplier portal's page**

Create `web-app/apps/supplier-portal/src/app/unauthorized/page.tsx` — identical
except for the second sentence of the paragraph, which names the other portal:

```tsx
"use client"

import { useClerk } from "@clerk/nextjs"
import { Button } from "@app/ui/button"

export default function UnauthorizedPage() {
  const { signOut } = useClerk()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-2xl font-semibold">Accesso non consentito</h1>
      <p className="text-muted-foreground max-w-md">
        Il tuo account non ha i permessi per accedere al portale fornitori.
        Contatta un amministratore se ritieni che si tratti di un errore.
      </p>
      <Button onClick={() => signOut({ redirectUrl: "/sign-in" })}>
        Esci
      </Button>
    </div>
  )
}
```

- [ ] **Step 3: Add the matcher and early return to `internal-portal/src/proxy.ts`**

Add a second matcher below the existing `isPublicRoute` declaration:

```ts
const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"])
// Reachable only when signed in, and deliberately NOT in isPublicRoute: this is
// where the role guard below sends people, so it has to sit outside that guard
// or it redirects to itself until the browser gives up.
const isUnauthorizedRoute = createRouteMatcher(["/unauthorized"])
```

Then insert the early return between `await auth.protect()` and the role check:

```ts
  // Enforce authentication
  await auth.protect()

  // The role guard's own destination. Signed in is enough to see it.
  if (isUnauthorizedRoute(req)) return

  // Enforce internal-portal access: project_manager, reviewer, or approver only.
```

- [ ] **Step 4: Add the same to `supplier-portal/src/proxy.ts`**

Identical matcher, identical early return, same position. The comment on the role
check below it differs — leave that line as it is.

- [ ] **Step 5: Type-check**

Run: `cd web-app && pnpm type-check`
Expected: exit 0.

- [ ] **Step 6: Lint and format**

Run: `make check-web`
Expected: clean.

- [ ] **Step 7: Verify the loop is gone**

With the internal portal's dev server running and signed out:

Run: `curl -sI http://localhost:3000/unauthorized | head -3`
Expected: a 307 to `/sign-in?redirect_url=...%2Funauthorized` — the route is
still behind auth.

Then sign in as a **supplier** in a browser at `http://localhost:3000` and
confirm you land on `/unauthorized` with the message rendered, once, with no
`ERR_TOO_MANY_REDIRECTS`. If no supplier dev user exists, the equivalent check
is to invert the guard temporarily — but prefer the real user; see
`docs/setup/clerk.md` for the role slugs.

Repeat on `http://localhost:3002` with an internal-role user.

- [ ] **Step 8: Commit**

```bash
git add web-app/apps/internal-portal/src/app/unauthorized/page.tsx \
        web-app/apps/supplier-portal/src/app/unauthorized/page.tsx \
        web-app/apps/internal-portal/src/proxy.ts \
        web-app/apps/supplier-portal/src/proxy.ts
git commit -m "fix(web): give /unauthorized a route and break the redirect loop

Both portals' role guards redirect a wrong-role user to /unauthorized, and
neither app defined it. Worse than a 404: the path matches the middleware
matcher, is not in isPublicRoute, and passes auth.protect() -- the user is
signed in, just in the wrong role -- so it reaches the same role check, fails
again, and redirects to itself. The browser ends on
ERR_TOO_MANY_REDIRECTS, which reads as a broken app rather than a
permissions message.

The early return goes after auth.protect() and before the role check rather
than into isPublicRoute: the page should still require a session, and
isPublicRoute means sign-in and sign-up.

The page sits outside the route group, so a user who cannot enter the portal
is not shown its chrome. This is an ordinary route segment, not Next's
reserved app/unauthorized.tsx -- the middleware issues a real redirect to a
real URL, which that convention does not handle."
```

---

### Task 5: Full-stack browser verification

The one place all four fixes are observed together, against built images rather
than a dev server — `NEXT_PUBLIC_*` values are inlined at build time, so Task 2
is not testable any other way.

**Files:** none modified.

**Interfaces:**
- Consumes: Tasks 1-4, all committed.
- Produces: the evidence that the branch is done.

- [ ] **Step 1: Rebuild both portal images**

Run: `make docker-build-web`
Expected: both images build. This gates on `check-contract`; if that fails, the
OpenAPI artifacts are stale for an unrelated reason — stop and report rather
than regenerating as part of this branch.

- [ ] **Step 2: Start the stack**

Run: `make docker-run-core`
Expected: internal portal on :3000, supplier portal on :3002, API on :8100.

- [ ] **Step 3: Confirm the live publishable key**

Run:
```bash
docker compose -f docker-compose.dev.yml exec internal-portal \
  sh -c 'grep -ro "pk_test_[A-Za-z0-9]*" .next 2>/dev/null | head -1'
```
Expected: the key from `.env.local`. A stale key here means the image predates
the rebuild and every check below is measuring the wrong build.

- [ ] **Step 4: Internal portal — sign in**

In the browser at `http://localhost:3000`, signed out. Expected: `/` →
`/home` → `/sign-in?redirect_url=...%2Fhome`. Sign in with an internal-role user.
Expected: lands on `/home`, renders, URL is `/home`. **Not** a blank page at `/`.

- [ ] **Step 5: Internal portal — console is clean**

With `/home` rendered, read the browser console. Expected: no
`Base UI: The \`render\` prop received a function named \`TooltipTrigger\`` warning
(Task 1), and no `afterSignInUrl`/`afterSignUpUrl` deprecation warnings
(Task 2). Clerk's development-keys notice is expected and fine. Note any other
pre-existing warning rather than chasing it.

- [ ] **Step 6: Internal portal — sidebar tooltips still work**

Collapse the sidebar. Expected: tooltips appear on the nav buttons when
collapsed and not when expanded. Open the Settings dialog from the sidebar —
that button is the one place a tooltip override and a Base UI `render` slot
stack, so it is what proves the ref chain survived. Expected: the dialog opens,
and Escape closes it and returns focus to the trigger.

- [ ] **Step 7: Internal portal — sign out**

Click sign out. Expected: lands on a bare `/sign-in`, with no `?redirect_url=`
(Task 3's `signOut({ redirectUrl })`), and no flash through `/`.

- [ ] **Step 8: Internal portal — wrong role**

Sign in with a supplier-role user at `http://localhost:3000`. Expected: the
`/unauthorized` page renders once with the Italian message and a working
sign-out button. No `ERR_TOO_MANY_REDIRECTS`.

- [ ] **Step 9: Supplier portal — repeat steps 4-8**

Same walkthrough at `http://localhost:3002`, with the roles swapped: a
supplier-role user signs in successfully, an internal-role user lands on
`/unauthorized`.

- [ ] **Step 10: Tear down**

Run: `make docker-stop`

- [ ] **Step 11: Final gate**

Run: `cd web-app && pnpm type-check && cd .. && make check-web`
Expected: both clean.

Run: `git log --oneline main..HEAD`
Expected: four commits, one per Task 1-4.

---

## Out of scope, deliberately

Recorded here so a reviewer does not read them as omissions:

- **`scripts/clerk/` setup tooling** (the other half of the fork's PR #1). It
  needs org creation, four custom org roles and memberships — API surface the
  fork's B2C version never touched — and gets its own design.
- **The `@app/ui` three-way split** (the fork's PR #2). Separately planned; the
  case for it is stronger here, since 12 of 21 app source files are byte-identical
  across the two portals.
- **`hub-nav.ts` being identical in both portals.** Suspicious — nav is exactly
  what two portals should differ on — but it is a domain question, not an auth
  bug.
- **The Dockerfile not copying `packages/*/node_modules`.** The fork found this
  necessary after its split (pnpm installs per-project, and the root holds almost
  nothing). It has not bitten here yet; it belongs to the split's plan.

# Web Package Split — Design

**Status:** approved, not yet implemented
**Ports:** [`tiziaco/fullstack-b2c-nextjs-fastapi-template` PR #2](https://github.com/tiziaco/fullstack-b2c-nextjs-fastapi-template/pull/2) ("Refactor/split UI package"), adapted for two portals

---

## Goal

Split `@app/ui` into three layers — `@app/core` ← `@app/ui` ← `@app/components` — and
use the new boundaries to remove the code that is currently duplicated byte-for-byte
between the internal and supplier portals.

No behaviour changes. Nothing user-facing, with one exception noted in §6 (a settings
heading changes from "Aspect" to "Appearance").

---

## Why, and why the reasoning differs from the fork's

The B2C fork split its UI package for a **hypothetical React Native target**: the
primitives layer is the one that would not survive an Expo port, so anything genuinely
portable belongs beneath it in a package that cannot reach for a renderer.

That argument holds here too, but it is not the one that pays for this work. This repo
has a second reason the fork did not have — **two portals that currently duplicate almost
everything**:

| | Files |
|---|---|
| **Byte-identical across both portals** | `clerk-user-panel.tsx`, `settings-dialog.tsx`, `server-status.tsx`, `sections/general-section.tsx`, `use-server-status.ts`, `query-provider.tsx`, `env-helpers.ts`, `messages.ts`, `lib/utils.ts`, `hub-nav.ts`, `styles/globals.css`, the sign-in page, and all five `(dashboard)`/`(portal)` route files |
| **Genuinely different** | `proxy.ts` (8 lines), `app/layout.tsx` (4 lines — title and description), `app/unauthorized/page.tsx` (2 lines) |
| **Internal portal only** | the sign-up page |

21 of 26 comparable files are identical. `cn()` exists in **three** copies — both apps
and `packages/ui`. The five auth fixes shipped in `2026-09-17-clerk-auth-fixes-port.md`
each had to be applied twice, in two files, because of this.

---

## The rule this design turns on

The fork's placement rule, from its `web-app/README.md`:

> A component composed out of those primitives, with no Clerk or API-client wiring,
> belongs in `packages/components`. One bound to **this app's** auth, routes or API
> payloads belongs in `apps/web/src/components/`.

With one app, "this app's auth" and "the shared auth package" are the same object, so the
distinction was never tested. Here they are different objects: two portals, one
`@app/auth`, one FastAPI server. `useServerStatus` is not bound to the internal portal's
API — it is bound to `/ready` on the one server both portals call.

**The rule is therefore read as: what belongs in an app is wiring that is *app-specific*,
not wiring that merely touches Clerk or the API client.** Shared infrastructure that both
portals hit identically moves into the package it is already coupled to.

`@app/components` keeps exactly the dependency set the fork gave it —
`@app/core`, `@app/ui`, `lucide-react`, peer `next`/`react`. **Its `package.json` is the
proof of the boundary**, and this design does not weaken it.

### The dependency direction constraint

One tempting placement is rejected on these grounds. Moving `clerk-user-panel.tsx` into
`@app/auth` would make `@app/auth` depend on `@app/components` (for `UserDetailsPanel`),
and because `@app/api-client` already declares `@app/auth` as a dependency, every consumer
of the API client would transitively pull in the whole UI stack. A logic package must not
depend on a UI package.

`clerk-user-panel.tsx` therefore **stays in both apps**, which is also the correct answer
on its own merits: it is already a 33-line wiring adapter over the presentational
`UserDetailsPanel`, and the `role === Role.PROJECT_MANAGER` branch that enables the
organization-profile action is meaningful in the internal portal and dead in the supplier
portal. Duplicating the adapter is the fork's design working as intended.

---

## 1. Target structure

```
web-app/packages/
├── core/          platform-free: no renderer, compiled without the DOM lib
├── ui/            web-only primitives (shadcn / Base UI)
├── components/    composed chrome, built on ui — no Clerk, no API client
├── auth/          unchanged
└── api-client/    + the two shared data-infrastructure modules
```

```
@app/core  ←  @app/ui  ←  @app/components  ←  apps/*
@app/core  ←  @app/api-client  →  @app/auth  ←  apps/*
```

Acyclic, and no package depends on a layer above it.

---

## 2. `@app/core` — new

Everything with no render dependency.

| Path | From |
|---|---|
| `src/lib/utils.ts` | `packages/ui/src/lib/utils.ts` (and deletes both apps' copies) |
| `src/lib/env.ts` | `apps/*/src/lib/env-helpers.ts` |
| `src/types/nav.ts` | `packages/ui/src/types/nav.ts` |
| `src/constants/messages.ts` | `apps/*/src/lib/messages.ts` |

**`package.json`** — subpath-only, no barrel, so importers name the layer they reach into
(`@app/core/lib/utils`, `@app/core/types/nav`):

```json
{
  "name": "@app/core",
  "version": "0.0.1",
  "private": true,
  "exports": {
    "./package.json": "./package.json",
    "./*": "./src/*.ts"
  },
  "dependencies": { "clsx": "^2.1.1", "tailwind-merge": "^3.0.0" },
  "peerDependencies": { "react": "^19.0.0" },
  "peerDependenciesMeta": { "react": { "optional": true } },
  "devDependencies": { "@types/react": "^19.2.14", "typescript": "^5.9.3" }
}
```

The `*` in an exports pattern spans `/`, so `@app/core/lib/utils` resolves to
`./src/lib/utils.ts`. `./package.json` is declared explicitly because a literal key beats
any pattern — without it, a tool resolving `@app/core/package.json` would be routed into
`src/package.json.ts`.

**`tsconfig.json`** — the enforcement, copied from the fork:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    // No "dom". This package must stay renderer-agnostic: a web-only global
    // like `window` has to fail here, not in review.
    //
    // "skipLibCheck" is load-bearing alongside it, not incidental tidiness:
    // @types/react-dom's own declarations reference DOM types, so flipping it
    // to false detonates this package. The two settings travel together.
    "lib": ["esnext"],
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx"
  },
  "include": ["**/*.ts"],
  "exclude": ["node_modules"]
}
```

**`NavItem.icon` is retyped structurally** so core depends on no icon library. Lucide
components stay assignable, so no call site changes:

```ts
import type { ComponentType } from "react"

export type NavItem = {
  title: string
  url: string
  icon?: ComponentType<{ className?: string }>
  items?: Array<{ title: string; url: string }>
}
```

Both renderers call it as `{item.icon && <item.icon />}`
(`nav-sidebar.tsx:42,80`), so the no-props contract is satisfied.

### Divergence from the fork: `env.ts`

The fork left `env-helpers.ts` in its app. Here it is shared by two portals and by
`query-provider`, so it moves into core — but `process` is not in `lib: ["esnext"]`, and
adding `@types/node` to get it would also hand core `fetch`, `URL` and `setTimeout`,
weakening the enforcement this package exists for. Declare the one global narrowly
instead:

```ts
// `process.env.NODE_ENV` is defined by every bundler this package could run
// under, Metro included, so it does not violate the no-renderer rule. Declared
// narrowly rather than pulling in @types/node, which would also make `fetch`
// and `setTimeout` resolve here and blunt the point of lib: ["esnext"].
declare const process: { env: { NODE_ENV?: string } }

const nodeEnv = process.env.NODE_ENV || "development"

export const isDevelopment = nodeEnv === "development"
export const isProduction = nodeEnv === "production"
export const isTest = nodeEnv === "test"
```

---

## 3. `@app/ui` — restructured

**`src/components/ui/` → `src/primitives/`.** A folder named `ui` inside a package named
`ui` is a single-app convention (`components/ui/` separating generated primitives from
components you wrote) carried into a package where the package name already draws that
line. shadcn's own monorepo template does not nest this way.

**`src/components/layout/` → `@app/components`** (§4).

**`src/lib/utils.ts` and `src/types/nav.ts` → `@app/core`** (§2), and their re-exports
come out of `src/index.ts`.

**Exports become wildcard-based**, so `shadcn add` no longer requires editing
`package.json` — which the current hand-written 24-entry map does:

```json
"exports": {
  ".": "./src/index.ts",
  "./package.json": "./package.json",
  "./styles/globals.css": "./src/styles/globals.css",
  "./hooks/*": "./src/hooks/*.ts",
  "./*": "./src/primitives/*.tsx"
}
```

Consumers are unaffected: `@app/ui/button` still resolves. Node matches a literal key
before any pattern and then prefers the longest pattern prefix, so `./styles/globals.css`
and `./hooks/*` still win over the catch-all.

This also fixes a live bug: **`src/hooks/use-mobile.ts` is exported from the barrel today
but has no `exports` entry**, so `@app/ui/hooks/use-mobile` does not resolve.

**Two barrel gaps get closed.** `AvatarBadge` and `SidebarFooterMenu` are exported from
their source files and missing from `src/index.ts` — the failure mode of a hand-maintained
barrel. `app-sidebar.tsx` needs `SidebarFooterMenu` across a package boundary after §4.

**`package.json` dependency changes:** add `@app/core`; remove `clsx` and `tailwind-merge`
(they move to core); remove `next` from `peerDependencies` — verified that no file under
`src/primitives/` imports `next/*` or `next` once `layout/` has moved.

The barrel stays hand-maintained. That is deliberate — it is worth the friction for a
19-export public surface — but it means **a new primitive is importable as `@app/ui/<name>`
immediately and missing from `@app/ui` until someone edits `src/index.ts`**. This has
already happened twice.

---

## 4. `@app/components` — new

| Path | From |
|---|---|
| `src/layout/app-sidebar.tsx` | `packages/ui/src/components/layout/` |
| `src/layout/nav-sidebar.tsx` | ″ |
| `src/layout/user-panel.tsx` | ″ |
| `src/layout/company-logo.tsx` | ″ |
| `src/settings/settings-dialog.tsx` | both apps' `components/settings/settings-dialog.tsx` |
| `src/settings/server-status-indicator.tsx` | the presentational half of both apps' `server-status.tsx` (§5) |

These are not primitives. They know the app's nav shape, its user model and its branding,
and they reach for `next/image`, `next/link` and `usePathname` — none of which a React
Native target can run. Separating them gives the boundary a compiler behind it: `@app/ui`
can no longer import them, so it cannot accrue app knowledge by accident.

**They import `@app/ui` by subpath, not through its barrel.** `user-panel` needs five
primitives; a barrel import would pull all nineteen into the client graph of everything
that renders it.

```json
{
  "name": "@app/components",
  "version": "0.0.1",
  "private": true,
  "exports": {
    "./package.json": "./package.json",
    "./*": "./src/*.tsx"
  },
  "dependencies": {
    "@app/core": "workspace:*",
    "@app/ui": "workspace:*",
    "lucide-react": "^1.8.0"
  },
  "peerDependencies": { "next": ">=16.0.0", "react": "^19.0.0" },
  "devDependencies": { "@types/react": "^19.2.14", "@types/react-dom": "^19.2.3", "typescript": "^5.9.3", "eslint": "^9", "eslint-config-next": "16.2.3" }
}
```

`tsconfig.json` is the current `packages/ui` one with the `paths` block dropped.
`eslint.config.mjs` mirrors `packages/ui`'s, with `@next/next/no-html-link-for-pages`
switched off — this is a library, not a Next app, so the rule that looks for a `pages/`
directory has nothing to find.

**No shim is possible for the `layout/` move.** An `exports` target cannot point outside
its own package, so the moment `layout/` leaves `packages/ui` the `@app/ui/layout/*`
specifiers are dead. Both apps' `layout.tsx` imports must be rewritten in the same commit.

---

## 5. The two presentational/wiring splits

`ServerHealthIndicator` is ~140 identical lines of `HoverCard` markup whose only
impurities are one `useServerStatus()` call and one module-load `isDevelopment` read.
Pushing both up into a thin app wrapper is the same move `footerSlot` makes, one level
deeper.

**`@app/components/settings/server-status-indicator.tsx`** — presentational, props-in,
no `@app/api-client` import:

The `status` value is `@app/api-client`'s generated `GetReadinessResponse` zod output,
which `@app/components` may not import. Declare it structurally in this file, covering
exactly the fields the markup reads, all optional. The app wrapper passes the generated
value, which is structurally assignable:

```tsx
/** Structural mirror of @app/api-client's GetReadinessResponse. Declared here
    rather than imported: this package must not depend on the API client. */
interface ServerStatus {
  status?: string
  version?: string
  environment?: string
  timestamp?: string
  components?: {
    api?: string
    database?: { status?: string }
    agents?: { chatbot?: { ready?: boolean } }
  }
}

interface ServerStatusIndicatorProps {
  status?: ServerStatus
  isLoading: boolean
  error: unknown
  /** Show the hover-card breakdown. Hoisted from a module-load env read so the
      component renders both branches under test. */
  showDetail?: boolean
}
```

Hoisting `isDevelopment` to a prop also removes the trap the fork documented in its
testing skill: a module-load `isDevelopment` makes a passing test cover half its
component.

**`apps/*/src/components/settings/server-status.tsx`** becomes the wiring, in both apps:

```tsx
"use client"

import { useServerStatus } from "@app/api-client/use-server-status"
import { ServerStatusIndicator } from "@app/components/settings/server-status-indicator"
import { isDevelopment } from "@app/core/lib/env"

export function ServerHealthIndicator() {
  const { status, isLoading, error } = useServerStatus()
  return (
    <ServerStatusIndicator
      status={status}
      isLoading={isLoading}
      error={error}
      showDetail={isDevelopment}
    />
  )
}
```

### Moving into `@app/api-client`

| Path | From |
|---|---|
| `src/use-server-status.ts` | both apps' `hooks/use-server-status.ts` |
| `src/query-provider.tsx` | both apps' `providers/query-provider.tsx` |

Both are infrastructure for the one server both portals call, and both are tightly coupled
to this package already: `use-server-status` exists to recover a 503 body out of
`ApiError` and relies on the `meta.silentError` convention that `query-provider`
implements. Splitting them across three files in two apps is what makes that pairing
invisible.

Hand-written files are safe here: orval's `clean: true` is scoped to
`src/generated/{endpoints,types,zod}`, and `src/errors.ts`, `src/use-api-fetch.ts` and
`src/index.ts` already live alongside it. `make gen-contract` will not touch them.

`package.json` gains `@app/core` (for `messages` and `isDevelopment`), `sonner`, and
`@tanstack/react-query-devtools`; `exports` gains `"./use-server-status"` and
`"./query-provider"`.

---

## 6. The settings rename

Ported from fork commits `c2cbea6` and `e008051`.

"Section" currently means three things across two files: `SettingSection` (the `@app/ui`
primitive), `SettingsSection` (the `{id,label,icon,content}` descriptor) and
`GeneralSection` (the content one descriptor points at). Only the first is a section. The
descriptor renders a left-rail entry, so it is a **tab**; the content is the General tab's
**settings**.

| Before | After |
|---|---|
| `interface SettingsSection` | `interface SettingsTab` |
| `SettingsDialogProps.sections` | `.tabs` |
| `activeSection` / `setActiveSection` | `activeTab` / `setActiveTab` |
| `sections.map((section) => …)` | `tabs.map((tab) => …)` |
| `const SETTINGS_SECTIONS = [...]` | `const SETTINGS_TABS: SettingsTab[] = [...]` |
| `export function GeneralSection()` | `GeneralSettings()` |
| `components/settings/sections/general-section.tsx` | `components/settings/general-settings.tsx` |
| `<SettingSection title="Aspect">` | `title="Appearance"` |

`SettingsSection` is currently exported and never imported, which leaves
`SETTINGS_SECTIONS` an untyped literal checked only structurally at the prop site.
Annotating it `SettingsTab[]` moves a malformed entry's error to the entry.

"Aspect" reads as a carry-over from *aspetto*; the English convention for this setting is
"Appearance". This is the design's one visible change.

The `sections/` directory disappears — it held one file.

### `footerSlot`

One line held `SettingsDialog` in the apps: a hardcoded `<ServerHealthIndicator />` in its
footer. It becomes a slot, the same seam `AppSidebar` already uses for `settingsSlot` and
`userSlot`:

```tsx
interface SettingsDialogProps {
  tabs: SettingsTab[]
  trigger?: React.ReactElement
  footerSlot?: React.ReactNode
}
```

```diff
-            <SidebarFooter>
-              <ServerHealthIndicator />
-            </SidebarFooter>
+            {footerSlot && <SidebarFooter>{footerSlot}</SidebarFooter>}
```

---

## 7. What each app keeps, and why

Both portals' `src/` retain, in duplicate:

| File | Why it stays duplicated |
|---|---|
| `lib/hub-nav.ts` | per-portal by definition — the internal portal's nav is not the supplier portal's, identical today only because both are scaffolding |
| `components/settings/general-settings.tsx` | the shipped example a fork is meant to **rewrite, not configure**. It imports only `@app/ui` and `next-themes`, so the placement rule says "promote" — and it stays anyway. Its body *is* the customization, and `SETTINGS_TABS` is the extension point it hangs off. Duplicating it is the demonstration that each portal owns its settings surface. |
| `components/layout/clerk-user-panel.tsx` | a 33-line wiring adapter; promoting it would invert the dependency graph (§"The rule this design turns on") |
| `components/settings/server-status.tsx` | ~12 lines of wiring after §5 |
| `app/(dashboard\|portal)/layout.tsx` | the assembly diagram. Someone forking this reads it to learn how a portal is composed; collapsing it to eight lines of config hides the thing the template exists to teach. |
| `styles/globals.css` | Tailwind entry point, one per app by construction |
| `app/layout.tsx`, `proxy.ts`, `app/unauthorized/page.tsx` | already genuinely different |
| route groups and their pages | the example domain |

Duplication falls from roughly 450 lines to roughly 190, and every remaining line is
wiring, config or domain rather than logic.

---

## 8. Mechanics with no safety net

Each of these fails silently or fails somewhere that does not point at the cause.

**Tailwind `@source`.** Tailwind scans filesystem paths, not package graphs. Both apps'
`styles/globals.css` needs a line added:

```css
@source "../../../../packages/ui/src";
@source "../../../../packages/components/src";
```

A missing entry costs nothing at type-check or build time and simply renders the chrome
unstyled. Verify against `h-125` and `max-w-2xl!` — they exist nowhere else in the repo
and set the settings dialog's whole geometry.

**`transpilePackages`.** Both apps' `next.config.ts` currently lists
`["@app/ui", "@app/auth", "@app/api-client"]` and must gain `@app/core` and
`@app/components`.

**Dockerfile manifest copies.** `web-app/Dockerfile:14-16` must gain
`COPY packages/core/package.json ./packages/core/` and the same for `components`.
`pnpm install --frozen-lockfile` fails on a lockfile naming a workspace project whose
`package.json` is absent.

> Checked and **not** a problem, contrary to the fork's finding: the builder stage copies
> no `node_modules` for `packages/*`, but a build to the `builder` target reaches
> `✓ Compiled successfully` — resolution of `@base-ui/react` from `packages/ui/src`
> works today. Do not "fix" this as part of the split.

**`pnpm-workspace.yaml`** already globs `packages/*`; no edit needed.

**Root `type-check`** is `pnpm -r exec tsc --noEmit`, so a new package with its own
`tsconfig.json` is picked up automatically. Root `lint` is `pnpm -r --if-present lint`, so
`@app/components` needs a `lint` script for its ESLint config to run at all.

**`@app/core`'s tsconfig is deliberately fragile.** The error `window` produces there
looks like a misconfiguration if you do not know it is intentional. Say so in the tsconfig
comment, and never flip `skipLibCheck` off.

---

## 9. Documentation to update

Every tree diagram and every path-by-name reference:

- `CLAUDE.md:29`, `README.md:14,95`
- `web-app/CLAUDE.md:17,50,120,137,237,246`
- `web-app/README.md:17,69,78,88,91,94` — the shadcn workflow still names
  `packages/ui/src/components/ui/`
- `web-app/apps/{internal,supplier}-portal/README.md:122,147,151` (and `:124,151,155`) —
  `company-logo.tsx` is referenced by path
- `docs/setup/making-it-yours.md:66` — `company-logo.tsx` by path; and the frontend
  identity table gains `messages.toasts` at its new `@app/core` location

Add, because none of it is inferable from the tree: the three-package rationale, where a
new component goes now that there are three places it could go, the slot pattern as the
promotion mechanism, and the four silent failure modes from §8.

`docs/superpowers/plans/` and `docs/superpowers/specs/` are historical records and are
**not** updated.

---

## 10. Out of scope

- The fork's `scripts/clerk/` setup tooling. Needs orgs, four custom org roles and
  memberships here — a larger job than the B2C version, and unrelated to this one.
- Deduplicating the route groups, the sign-in page or the domain pages. Those are the
  example domain; they are meant to be replaced, not shared.
- A `@app/portal-shell` package that would collapse both `layout.tsx` files. Considered
  and rejected in §7.
- Tests. This repo has no Vitest setup; the fork's co-located tests do not port.
- Both READMEs label a route-group child `(app)/` where the real directories are
  `(auth)/` + `(dashboard)/`/`(portal)/`. Pre-existing, unrelated, left alone.

---

## 11. Verification

1. `pnpm install` from `web-app/` — lockfile accepts two new workspace projects.
2. `pnpm type-check` — passes across all seven projects. Confirm `@app/core` is among
   them.
3. Add `const x = window` to a `packages/core/src/` file; `pnpm type-check` fails with
   **TS2304**. Revert.
4. `make check-web` — ESLint and Prettier clean, `@app/components` included.
5. `pnpm build` — both portals build.
6. Delete an `@source` line, rebuild, and confirm the emitted CSS loses `h-125` and
   `max-w-2xl!`. Restore. This is the only way to prove the line is doing work.
7. `git grep -n "@app/ui/layout/"` returns nothing.
8. `git grep -n "components/ui/"` returns nothing outside `docs/superpowers/`.
9. Both portals, in a browser: sidebar renders styled and collapses; tooltips show the
   right label; the settings dialog opens at its correct geometry with the server
   indicator in its footer; the theme select works; the user panel signs out to
   `/sign-in`. The supplier portal must be exercised too — its role-guard paths went
   unverified in the auth-fixes port.
10. `docker build --target builder` for one portal reaches `✓ Compiled successfully`.

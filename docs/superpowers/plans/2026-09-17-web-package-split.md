# Web Package Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `@app/ui` into `@app/core` ← `@app/ui` ← `@app/components`, and use the new boundaries to delete the code currently duplicated byte-for-byte between the internal and supplier portals.

**Architecture:** Three layers by what survives a React Native port — platform-free code below the primitives, web-only primitives, composed chrome above them. `@app/components` is kept free of Clerk and the API client; shared code that touches those moves into the package it is already coupled to (`@app/api-client`), and app-*specific* wiring stays in each portal. Two components are split presentational-half / wiring-half so the bulk can be shared while the impure call stays in the app.

**Tech Stack:** pnpm workspaces, TypeScript 5.9, Next.js 16 App Router, React 19, Tailwind CSS v4, shadcn/Base UI, orval-generated API client.

**Spec:** `docs/superpowers/specs/2026-09-17-web-package-split-design.md`

## Global Constraints

- `@app/components`'s `dependencies` are exactly `@app/core`, `@app/ui`, `lucide-react`, with `next` and `react` as peers. **Never** add `@clerk/*` or `@app/api-client` to it — its `package.json` is the proof of the boundary.
- No package may depend on a layer above it. `@app/auth` and `@app/api-client` must never depend on `@app/ui` or `@app/components`.
- `@app/core` compiles with `"lib": ["esnext"]` and **no `"dom"`**. `"skipLibCheck": true` is load-bearing alongside it — `@types/react-dom`'s declarations reference DOM types — and must never be flipped off.
- **No behaviour changes**, with exactly one visible exception: the settings heading `"Aspect"` becomes `"Appearance"` (Task 5).
- The two portals are byte-identical in every file where they are byte-identical today, and must stay that way. Verify with the diff loop in each task's checks.
- Prettier config is `web-app/.prettierrc`, **semicolons off**. Run `make check-web` from the repo root before every commit.
- Italian UI copy stays Italian. The settings strings are already English and stay English.
- `packages/ui/src/index.ts` is hand-maintained on purpose. A new primitive is importable as `@app/ui/<name>` immediately via the wildcard but is **missing from `@app/ui`** until someone adds a line there.
- Commit messages: conventional-commit prefix, imperative subject, body explaining *why*. No `Co-Authored-By` or tool attribution.

## Verification commands (used throughout)

```bash
# from the repo root
make check-web                      # ESLint + Prettier across all workspace projects
cd web-app && pnpm type-check       # tsc --noEmit in every package
cd web-app && pnpm build            # next build, both portals
```

```bash
# the portal-parity invariant, from web-app/
for f in $(cd apps/internal-portal/src && find . -type f | sed 's|^\./||'); do
  b="apps/supplier-portal/src/$f"
  [ -f "$b" ] && ! diff -q "apps/internal-portal/src/$f" "$b" >/dev/null && echo "DIFFERS: $f"
done
# Expected output, always, at every commit — exactly these three:
#   DIFFERS: app/layout.tsx
#   DIFFERS: app/unauthorized/page.tsx
#   DIFFERS: proxy.ts
```

---

## File Structure

**Created:**

| Path | Responsibility |
|---|---|
| `web-app/packages/core/package.json` | subpath-only manifest, no barrel |
| `web-app/packages/core/tsconfig.json` | the no-DOM enforcement |
| `web-app/packages/core/src/lib/utils.ts` | `cn()` — the monorepo's only copy |
| `web-app/packages/core/src/lib/env.ts` | `isDevelopment` / `isProduction` / `isTest` |
| `web-app/packages/core/src/types/nav.ts` | `NavItem`, icon typed structurally |
| `web-app/packages/core/src/constants/messages.ts` | curated toast copy |
| `web-app/packages/components/package.json` | manifest — the boundary proof |
| `web-app/packages/components/tsconfig.json` | standard web tsconfig, no `paths` |
| `web-app/packages/components/eslint.config.mjs` | library lint config |
| `web-app/packages/components/src/layout/*.tsx` | the four composed layout components |
| `web-app/packages/components/src/settings/settings-dialog.tsx` | shared settings shell |
| `web-app/packages/components/src/settings/server-status-indicator.tsx` | presentational health widget |
| `web-app/packages/api-client/src/use-server-status.ts` | `/ready` polling + 503-body recovery |
| `web-app/packages/api-client/src/query-provider.tsx` | QueryClient + error→toast policy |

**Deleted:** both portals' `lib/utils.ts`, `lib/messages.ts`, `lib/env-helpers.ts`, `hooks/use-server-status.ts`, `providers/query-provider.tsx`, `components/settings/settings-dialog.tsx`; `packages/ui/src/lib/utils.ts`, `packages/ui/src/types/nav.ts`.

**Renamed:** `packages/ui/src/components/ui/` → `packages/ui/src/primitives/`; `packages/ui/src/components/layout/` → `packages/components/src/layout/`; both portals' `components/settings/sections/general-section.tsx` → `components/settings/general-settings.tsx`.

---

## Task 1: Create `@app/core` and point everything at it

**Files:**
- Create: `web-app/packages/core/package.json`, `web-app/packages/core/tsconfig.json`, `web-app/packages/core/src/lib/env.ts`, `web-app/packages/core/src/constants/messages.ts`
- Move: `web-app/packages/ui/src/lib/utils.ts` → `web-app/packages/core/src/lib/utils.ts`; `web-app/packages/ui/src/types/nav.ts` → `web-app/packages/core/src/types/nav.ts`
- Delete: `web-app/apps/{internal,supplier}-portal/src/lib/{utils.ts,messages.ts,env-helpers.ts}`
- Modify: 15 files under `web-app/packages/ui/src/components/ui/`, 2 under `.../components/layout/`, `web-app/packages/ui/src/index.ts`, `web-app/packages/ui/package.json`, both portals' `package.json`, `next.config.ts`, `src/lib/hub-nav.ts`, `src/components/settings/server-status.tsx`, `src/providers/query-provider.tsx`, `web-app/Dockerfile`

**Interfaces:**
- Produces: `@app/core/lib/utils` → `cn(...inputs: ClassValue[]): string`; `@app/core/lib/env` → `isDevelopment: boolean`, `isProduction: boolean`, `isTest: boolean`; `@app/core/types/nav` → `type NavItem = { title: string; url: string; icon?: ComponentType<{ className?: string }>; items?: Array<{ title: string; url: string }> }`; `@app/core/constants/messages` → `messages.toasts.{sessionExpired,forbidden,notFound,conflictError,validationError,genericError}`
- Consumes: nothing — this is the bottom of the stack.

- [ ] **Step 1: Create the package manifest**

`web-app/packages/core/package.json`:

```json
{
  "name": "@app/core",
  "version": "0.0.1",
  "private": true,
  "exports": {
    "./package.json": "./package.json",
    "./*": "./src/*.ts"
  },
  "dependencies": {
    "clsx": "^2.1.1",
    "tailwind-merge": "^3.0.0"
  },
  "peerDependencies": {
    "react": "^19.0.0"
  },
  "peerDependenciesMeta": {
    "react": {
      "optional": true
    }
  },
  "devDependencies": {
    "@types/react": "^19.2.14",
    "typescript": "^5.9.3"
  }
}
```

There is no `"."` entry and no barrel: importers name the layer they reach into. The `*` in an exports pattern spans `/`, so `@app/core/lib/utils` resolves to `./src/lib/utils.ts`. `./package.json` is declared because a literal key beats any pattern — without it, a tool resolving `@app/core/package.json` is routed into `src/package.json.ts`.

- [ ] **Step 2: Create the tsconfig — this is the enforcement**

`web-app/packages/core/tsconfig.json`. `tsc` parses `tsconfig.json` as JSONC, so the
comments below are part of the file and must be kept — the `lib` setting is the whole
point of this package and looks like a mistake without them:

```jsonc
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

- [ ] **Step 3: Move `cn` and `NavItem` into core**

```bash
cd web-app
mkdir -p packages/core/src/lib packages/core/src/types packages/core/src/constants
git mv packages/ui/src/lib/utils.ts packages/core/src/lib/utils.ts
git mv packages/ui/src/types/nav.ts packages/core/src/types/nav.ts
rmdir packages/ui/src/lib packages/ui/src/types
```

- [ ] **Step 4: Retype `NavItem.icon` structurally**

Replace the whole of `web-app/packages/core/src/types/nav.ts`:

```ts
import type { ComponentType } from "react"

/**
 * Sidebar navigation entry.
 *
 * `icon` is typed structurally rather than as lucide-react's `LucideIcon` so
 * this package stays free of any one icon library: lucide's components remain
 * assignable, and a native app rendering lucide-react-native satisfies the
 * same contract. Renderers call it with no props today.
 */
export type NavItem = {
  title: string
  url: string
  icon?: ComponentType<{ className?: string }>
  items?: Array<{
    title: string
    url: string
  }>
}
```

Both renderers call it as `{item.icon && <item.icon />}` (`nav-sidebar.tsx:42` and `:80`), so the no-props contract holds.

- [ ] **Step 5: Create `env.ts`**

`web-app/packages/core/src/lib/env.ts`:

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

- [ ] **Step 6: Move the toast copy into core**

```bash
cd web-app
git mv apps/internal-portal/src/lib/messages.ts packages/core/src/constants/messages.ts
git rm apps/supplier-portal/src/lib/messages.ts
git rm apps/internal-portal/src/lib/utils.ts apps/supplier-portal/src/lib/utils.ts
git rm apps/internal-portal/src/lib/env-helpers.ts apps/supplier-portal/src/lib/env-helpers.ts
```

The moved file's contents are unchanged — it is already platform-free.

- [ ] **Step 7: Rewrite every `cn` and `NavItem` import**

```bash
cd web-app
# 14 primitives import ../../lib/utils; sidebar.tsx uses the @/ alias
perl -pi -e 's{from "\.\./\.\./lib/utils"}{from "\@app/core/lib/utils"}' packages/ui/src/components/ui/*.tsx
perl -pi -e 's{from "\@/lib/utils"}{from "\@app/core/lib/utils"}' packages/ui/src/components/ui/*.tsx
# two layout components import the nav type
perl -pi -e 's{from "\.\./\.\./types/nav"}{from "\@app/core/types/nav"}' packages/ui/src/components/layout/*.tsx
# the apps
perl -pi -e 's{from "\@/lib/utils"}{from "\@app/core/lib/utils"}' apps/*/src/components/settings/server-status.tsx
perl -pi -e 's{from "\@/lib/env-helpers"}{from "\@app/core/lib/env"}' apps/*/src/components/settings/server-status.tsx
perl -pi -e 's{from "\.\./lib/env-helpers"}{from "\@app/core/lib/env"}' apps/*/src/providers/query-provider.tsx
perl -pi -e 's{from "\.\./lib/messages"}{from "\@app/core/constants/messages"}' apps/*/src/providers/query-provider.tsx
perl -pi -e 's{import type \{ NavItem \} from "\@app/ui"}{import type { NavItem } from "\@app/core/types/nav"}' apps/*/src/lib/hub-nav.ts
```

Verify nothing was missed:

```bash
grep -rn "lib/utils\|lib/env-helpers\|lib/messages\|types/nav" packages/ui/src apps/*/src
```

Expected: every hit says `@app/core/...`. No hit says `@/lib/`, `../../lib/`, `../lib/` or `./types/nav`.

- [ ] **Step 8: Drop the re-exports from the `@app/ui` barrel**

In `web-app/packages/ui/src/index.ts`, delete these four lines and the two comment headers above them:

```ts
// Utilities
export { cn } from "./lib/utils"

// Types
export type { NavItem } from "./types/nav"
```

There is deliberately no transitional shim. An `exports` target cannot point outside its own package, so a shim would have to be a re-export file, and the only consumer (`hub-nav.ts`) was already rewritten in Step 7.

- [ ] **Step 9: Move the dependencies**

In `web-app/packages/ui/package.json`, add `"@app/core": "workspace:*"` as the first entry of `dependencies`, and remove `"clsx"` and `"tailwind-merge"`.

In **both** `web-app/apps/internal-portal/package.json` and `web-app/apps/supplier-portal/package.json`: add `"@app/core": "workspace:*"` alongside the other `@app/*` entries, and remove `"clsx"` and `"tailwind-merge"` — nothing in either app references them now that `lib/utils.ts` is gone.

Leave `class-variance-authority` and `@base-ui/react` in the apps for now; they are removed in Task 3, where the Docker resolution check that gates it belongs.

- [ ] **Step 10: Register the package with the build**

In **both** apps' `next.config.ts`, line 5:

```diff
-  transpilePackages: ["@app/ui", "@app/auth", "@app/api-client"],
+  transpilePackages: ["@app/core", "@app/ui", "@app/auth", "@app/api-client"],
```

In `web-app/Dockerfile`, after line 14 (`COPY packages/api-client/package.json ...`):

```diff
 COPY packages/api-client/package.json ./packages/api-client/
 COPY packages/auth/package.json ./packages/auth/
+COPY packages/core/package.json ./packages/core/
 COPY packages/ui/package.json ./packages/ui/
```

`pnpm install --frozen-lockfile` fails on a lockfile naming a workspace project whose `package.json` is absent, so this is not optional.

`web-app/pnpm-workspace.yaml` already globs `packages/*`. No edit needed.

- [ ] **Step 11: Install and verify**

```bash
cd web-app && pnpm install
```

Expected: lockfile updates, `@app/core` appears as a workspace project.

```bash
cd web-app && pnpm type-check
```

Expected: PASS across all six projects. Confirm `@app/core` is among the directories tsc runs in.

- [ ] **Step 12: Prove the no-DOM enforcement actually works**

```bash
cd web-app
echo 'export const probe = window.location.href' > packages/core/src/probe.ts
pnpm type-check
```

Expected: **FAIL** in `packages/core`, with `error TS2304: Cannot find name 'window'.`

If it passes, the `lib` setting is not taking effect — stop and fix the tsconfig before continuing.

```bash
rm packages/core/src/probe.ts
cd web-app && pnpm type-check     # back to PASS
```

- [ ] **Step 13: Full check and commit**

```bash
make check-web
cd web-app && pnpm build
```

Both expected to pass. Then run the portal-parity loop from the header — expected output is exactly the three `DIFFERS:` lines.

```bash
git add -A
git commit -m "refactor(web): add @app/core for platform-free shared code

Extracts the code with no render dependency into its own package below
the UI layer: cn(), NavItem, the curated toast copy and the NODE_ENV
helpers. cn() existed in three copies -- both portals and packages/ui --
and every one of them was byte-identical.

The motivation is the same one the B2C fork had, plus one it did not:
React Native cannot run this repo's primitives, so the primitive layer is
the one that will not survive a port and anything genuinely portable
belongs beneath it; and with two portals, a shared helper duplicated per
app is a fix that has to be applied twice.

That 'cannot reach for a renderer' rule is enforced rather than
documented: packages/core builds with lib: [\"esnext\"] and no \"dom\", so
window in its own source is a type error. skipLibCheck travels with it --
@types/react-dom's declarations reference DOM types -- hence the comment
in its tsconfig.

NavItem's icon is now typed structurally instead of as lucide-react's
LucideIcon. Lucide components stay assignable, so no call site changes,
but core no longer depends on a web icon library.

The package is subpath-only with no barrel, so importers name the layer
they are reaching into: @app/core/lib/utils, @app/core/types/nav."
```

---

## Task 2: Rename `components/ui/` to `primitives/` and wildcard the exports

**Files:**
- Move: `web-app/packages/ui/src/components/ui/` → `web-app/packages/ui/src/primitives/` (19 files)
- Modify: `web-app/packages/ui/package.json`, `web-app/packages/ui/src/index.ts`, `web-app/packages/ui/components.json`, `web-app/packages/ui/src/components/layout/*.tsx` (4 files)

**Interfaces:**
- Consumes: `@app/core/lib/utils`, `@app/core/types/nav` (Task 1).
- Produces: `@app/ui/<name>` resolves to `src/primitives/<name>.tsx` for every primitive; `@app/ui/hooks/use-mobile` now resolves; `@app/ui` barrel additionally exports `AvatarBadge` and `SidebarFooterMenu`; `@app/ui/layout/*` still resolves (transitional, removed in Task 3).

- [ ] **Step 1: Move the directory**

```bash
cd web-app/packages/ui/src
git mv components/ui primitives
```

`components/layout/` stays put for now — it moves in Task 3.

- [ ] **Step 2: Fix the relative imports that crossed the moved boundary**

The four files in `components/layout/` import primitives as `../ui/<name>`. From `components/layout/`, the primitives are now at `../../primitives/`:

```bash
cd web-app/packages/ui/src
perl -pi -e 's{from "\.\./ui/}{from "\.\./\.\./primitives/}' components/layout/*.tsx
```

Inside `primitives/`, sibling imports (`./button` and the like) are unaffected by the move.

Verify:

```bash
grep -rn 'from "\.\./ui/' web-app/packages/ui/src
```

Expected: no output.

- [ ] **Step 3: Replace the export map with wildcards**

In `web-app/packages/ui/package.json`, replace the entire `"exports"` object — all 24 entries — with:

```json
  "exports": {
    ".": "./src/index.ts",
    "./package.json": "./package.json",
    "./styles/globals.css": "./src/styles/globals.css",
    "./hooks/*": "./src/hooks/*.ts",
    "./layout/*": "./src/components/layout/*.tsx",
    "./*": "./src/primitives/*.tsx"
  },
```

Consumers are unaffected: `@app/ui/button` still resolves. Node matches a literal key before any pattern, then prefers the longest pattern prefix — so `./styles/globals.css`, `./hooks/*` and `./layout/*` all win over the catch-all. `./package.json` is declared for the same reason as in core: without it, `@app/ui/package.json` would be routed into `src/primitives/package.json.tsx`.

`./hooks/*` fixes a live bug — `src/hooks/use-mobile.ts` is exported from the barrel today but has **no** `exports` entry, so `@app/ui/hooks/use-mobile` does not resolve.

`./layout/*` is **temporary**. `layout/` moves to `@app/components` in Task 3, which deletes this entry; it exists so this commit type-checks on its own.

- [ ] **Step 4: Repoint the barrel at the new directory**

In `web-app/packages/ui/src/index.ts`, rewrite every primitive import path:

```bash
cd web-app/packages/ui/src
perl -pi -e 's{from "\./components/ui/}{from "\./primitives/}' index.ts
```

- [ ] **Step 5: Close the two barrel gaps**

`AvatarBadge` and `SidebarFooterMenu` are exported from their source files and missing from `src/index.ts` — the failure mode of a hand-maintained barrel. `app-sidebar.tsx` needs `SidebarFooterMenu` across a package boundary in Task 3.

In `web-app/packages/ui/src/index.ts`, add `AvatarBadge` to the avatar export block:

```ts
export {
  Avatar,
  AvatarBadge,
  AvatarFallback,
  AvatarImage,
  AvatarGroup,
  AvatarGroupCount,
} from "./primitives/avatar"
```

and `SidebarFooterMenu` to the sidebar export block, in alphabetical position between `SidebarFooter` and `SidebarGroup`:

```ts
  SidebarFooter,
  SidebarFooterMenu,
  SidebarGroup,
```

Confirm nothing else is missing:

```bash
cd web-app/packages/ui/src
grep -ho "^export function [A-Za-z]*\|^function [A-Za-z]*" primitives/*.tsx \
  | sed 's/^export //;s/^function //' | sort -u \
  | while read n; do grep -q "\b$n\b" index.ts || echo "MISSING: $n"; done
```

Expected: no output.

- [ ] **Step 6: Update the shadcn config so the CLI generates into the right place**

In `web-app/packages/ui/components.json`, replace the `"aliases"` block:

```json
  "aliases": {
    "components": "@/components",
    "utils": "@app/core/lib/utils",
    "ui": "@/primitives",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
```

`utils` points across a package boundary on purpose — `cn` lives in `@app/core` now, and a component the CLI generates must import it from there. `packages/ui/tsconfig.json` keeps its `"paths": { "@/*": ["./src/*"] }` entry, which is what makes the `@/` aliases resolve.

- [ ] **Step 7: Verify and commit**

```bash
cd web-app && pnpm type-check && pnpm build
make check-web
```

All expected to pass. Then prove the new `./hooks/*` entry actually resolves, rather
than just checking it is present in the file — add a temporary import to a portal:

```bash
cd web-app
cat >> apps/internal-portal/src/lib/hub-nav.ts <<'EOF'

import { useIsMobile } from "@app/ui/hooks/use-mobile"
export const __probe = useIsMobile
EOF
pnpm type-check
```

Expected: PASS. Before the `./hooks/*` entry existed this failed with
`Cannot find module '@app/ui/hooks/use-mobile'`. Then revert:

```bash
cd web-app && git checkout apps/internal-portal/src/lib/hub-nav.ts && pnpm type-check
```

```bash
git add -A
git commit -m "refactor(ui): rename components/ui to primitives, wildcard the exports

packages/ui/src/components/ui/ put a folder named ui inside a package
named ui -- a single-app convention, where components/ui/ separates
generated primitives from components you wrote, carried into a package
where the package name already draws that line. shadcn's own monorepo
template does not nest this way.

Consumers are unaffected: the new \"./*\" -> \"./src/primitives/*.tsx\"
wildcard keeps imports bare, so @app/ui/button still resolves. It also
means adding a component no longer means editing package.json, which the
old hand-written 24-entry export map required. Node matches a literal key
before any pattern and then prefers the longest pattern prefix, so the
explicit ./styles/globals.css and ./hooks/* entries still win over the
catch-all. ./package.json is now declared for the same reason -- without
it a tool resolving @app/ui/package.json would be routed into
src/primitives/package.json.tsx.

./hooks/* also fixes a live bug: use-mobile.ts was exported from the
barrel with no exports entry, so @app/ui/hooks/use-mobile never resolved.

The barrel gains AvatarBadge and SidebarFooterMenu. Both were exported
from their source files and missing from src/index.ts, which is the
failure mode of a hand-maintained barrel and the reason it stays
hand-maintained only where it is worth it. app-sidebar.tsx needs
SidebarFooterMenu across a package boundary in the next commit.

./layout/* is a temporary export entry. layout/ moves to @app/components
next, which deletes it; it exists so this commit type-checks on its own."
```

---

## Task 3: Extract the composed layout into `@app/components`

**Files:**
- Create: `web-app/packages/components/{package.json,tsconfig.json,eslint.config.mjs}`
- Move: `web-app/packages/ui/src/components/layout/{app-sidebar,company-logo,nav-sidebar,user-panel}.tsx` → `web-app/packages/components/src/layout/`
- Modify: `web-app/packages/ui/package.json`, `web-app/packages/ui/src/index.ts`, both portals' `package.json`, `next.config.ts`, `src/styles/globals.css`, `src/app/(dashboard|portal)/layout.tsx`, `src/components/layout/clerk-user-panel.tsx`, `web-app/Dockerfile`

**Interfaces:**
- Consumes: `@app/core/types/nav` → `NavItem`; `@app/ui/<primitive>` subpaths; `@app/ui`'s `SidebarFooterMenu` (added in Task 2).
- Produces: `@app/components/layout/app-sidebar` → `AppSidebar({ items: NavItem[], logoSrc: string, logoAlt?: string, settingsSlot?: React.ReactNode, userSlot?: React.ReactNode, ...SidebarProps })`; `@app/components/layout/user-panel` → `UserDetailsPanel`, `type UserPanelUser`; `@app/components/layout/nav-sidebar` → `MenuNavigator`; `@app/components/layout/company-logo` → `CompanyLogo`.

- [ ] **Step 1: Create the manifest — this file is the boundary**

`web-app/packages/components/package.json`:

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
  "peerDependencies": {
    "next": ">=16.0.0",
    "react": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.2.14",
    "@types/react-dom": "^19.2.3",
    "typescript": "^5.9.3",
    "eslint": "^9",
    "eslint-config-next": "16.2.3"
  },
  "scripts": {
    "lint": "eslint"
  }
}
```

The `lint` script is required: the repo's root `lint` is `pnpm -r --if-present lint`, so without it this package's ESLint config never runs.

- [ ] **Step 2: Create the tsconfig**

`web-app/packages/components/tsconfig.json` — the current `packages/ui` config with the `paths` block dropped (nothing here uses the `@/` alias):

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
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
  "include": ["**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create the ESLint config**

`web-app/packages/components/eslint.config.mjs` — identical to `packages/ui/eslint.config.mjs`:

```js
import { defineConfig, globalIgnores } from "eslint/config"
import nextVitals from "eslint-config-next/core-web-vitals"
import nextTs from "eslint-config-next/typescript"

// Same rules as the portals. This package is a library, not a Next app, so the
// rule that looks for a pages/ directory is switched off.
const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  { rules: { "@next/next/no-html-link-for-pages": "off" } },
  globalIgnores(["dist/**", "build/**"]),
])

export default eslintConfig
```

- [ ] **Step 4: Move the four components**

```bash
cd web-app
mkdir -p packages/components/src/layout
git mv packages/ui/src/components/layout/app-sidebar.tsx   packages/components/src/layout/
git mv packages/ui/src/components/layout/company-logo.tsx  packages/components/src/layout/
git mv packages/ui/src/components/layout/nav-sidebar.tsx   packages/components/src/layout/
git mv packages/ui/src/components/layout/user-panel.tsx    packages/components/src/layout/
rmdir packages/ui/src/components/layout packages/ui/src/components
```

These are not primitives. They know the app's nav shape, its user model and its branding, and they reach for `next/image`, `next/link` and `usePathname` — none of which a React Native target can run.

- [ ] **Step 5: Rewrite their imports to cross the package boundary**

```bash
cd web-app/packages/components/src/layout
perl -pi -e 's{from "\.\./\.\./primitives/([a-z-]+)"}{from "\@app/ui/$1"}' *.tsx
```

`app-sidebar.tsx` additionally imports `SidebarFooterMenu`, which lives in the sidebar primitive — after the rewrite its import block reads:

```tsx
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarFooterMenu,
  SidebarGroup,
  SidebarHeader,
  SidebarMenuItem,
} from "@app/ui/sidebar"
import { MenuNavigator } from "./nav-sidebar"
import { CompanyLogo } from "./company-logo"
import type { NavItem } from "@app/core/types/nav"
```

Import by **subpath, not the barrel**: `user-panel` needs five primitives, and a barrel import would pull all nineteen into the client graph of everything that renders it.

Verify:

```bash
grep -rn 'from "\.\./\.\./primitives' web-app/packages/components/src   # expect no output
grep -rn 'from "@app/ui"' web-app/packages/components/src               # expect no output — subpaths only
```

- [ ] **Step 6: Drop the layout exports from `@app/ui`**

In `web-app/packages/ui/package.json`, remove the transitional entry added in Task 2:

```diff
-    "./layout/*": "./src/components/layout/*.tsx",
```

In `web-app/packages/ui/src/index.ts`, delete the trailing `// Layout` block:

```ts
// Layout
export { AppSidebar } from "./components/layout/app-sidebar"
export { MenuNavigator } from "./components/layout/nav-sidebar"
export { UserDetailsPanel } from "./components/layout/user-panel"
export type { UserPanelUser } from "./components/layout/user-panel"
export { CompanyLogo } from "./components/layout/company-logo"
```

Also remove `"next"` from `packages/ui`'s `peerDependencies` — verified that no file under `src/primitives/` imports `next` or `next/*` once `layout/` has gone.

**There is no shim available here.** An `exports` target cannot point outside its own package, so the moment `layout/` leaves `packages/ui` the `@app/ui/layout/*` specifiers are dead. Step 7 must land in the same commit.

- [ ] **Step 7: Rewrite the app imports**

Three call sites per portal, six in total:

```bash
cd web-app
perl -pi -e 's{from "\@app/ui/layout/app-sidebar"}{from "\@app/components/layout/app-sidebar"}' \
  "apps/internal-portal/src/app/(dashboard)/layout.tsx" "apps/supplier-portal/src/app/(portal)/layout.tsx"
perl -pi -e 's{from "\@app/ui/layout/user-panel"}{from "\@app/components/layout/user-panel"}' \
  apps/*/src/components/layout/clerk-user-panel.tsx
```

Verify:

```bash
git grep -n "@app/ui/layout/"    # expect no output
```

- [ ] **Step 8: Register the package — build, styles, Docker**

Both apps' `package.json`: add `"@app/components": "workspace:*"` alongside the other `@app/*` entries, and now remove `"class-variance-authority"` and `"@base-ui/react"` — neither appears anywhere in either app's `src/`, and `packages/ui` declares both itself.

Both apps' `next.config.ts`:

```diff
-  transpilePackages: ["@app/core", "@app/ui", "@app/auth", "@app/api-client"],
+  transpilePackages: [
+    "@app/core",
+    "@app/ui",
+    "@app/components",
+    "@app/auth",
+    "@app/api-client",
+  ],
```

Both apps' `src/styles/globals.css`, line 5:

```diff
 @source "../../../../packages/ui/src";
+@source "../../../../packages/components/src";
```

**This line has no safety net.** Tailwind scans filesystem paths, not package graphs, so a missing entry costs nothing at type-check or build time and simply renders the sidebar unstyled.

`web-app/Dockerfile`, in the deps stage:

```diff
 COPY packages/auth/package.json ./packages/auth/
+COPY packages/components/package.json ./packages/components/
 COPY packages/core/package.json ./packages/core/
 COPY packages/ui/package.json ./packages/ui/
```

- [ ] **Step 9: Verify, including the two checks with no compiler behind them**

```bash
cd web-app && pnpm install && pnpm type-check && pnpm build
make check-web
```

Then prove the Tailwind `@source` line is doing work — the only way to test it:

```bash
cd web-app
grep -rc "h-125\|max-w-2xl" apps/internal-portal/.next/static/css/*.css
```

Expected: a non-zero count. `h-125` and `max-w-2xl!` exist nowhere else in the repo and set the settings dialog's whole geometry. If the count is zero, an `@source` line is missing or wrong.

Then confirm removing `@base-ui/react` from the apps did not break module resolution in the container, where per-package `node_modules` are not copied:

```bash
cd /path/to/repo/root
docker build -f web-app/Dockerfile --target builder \
  --build-arg APP_NAME=internal-portal \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_placeholder \
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8100 \
  -t tmp-split-check web-app 2>&1 | tee /tmp/split-docker.log
grep -c "Compiled successfully" /tmp/split-docker.log
docker rmi tmp-split-check
```

Expected: **`✓ Compiled successfully`** appears. The build then fails at prerender with an invalid-publishable-key error — that is expected and means compilation and module resolution both succeeded. A `Module not found` error before that point is a real failure; the fix is to add per-package `node_modules` copies to the builder stage:

```dockerfile
COPY --from=deps /app/packages/ui/node_modules ./packages/ui/node_modules
COPY --from=deps /app/packages/components/node_modules ./packages/components/node_modules
```

Finally, run the portal-parity loop — still exactly three `DIFFERS:` lines.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(web): extract composed layout into @app/components

AppSidebar, MenuNavigator, UserDetailsPanel and CompanyLogo are not
primitives. They know the app's nav shape, its user model and its
branding, and they reach for next/image, next/link and usePathname --
none of which a React Native target can run. Separating them from the
primitives gives the boundary a compiler behind it: @app/ui can no longer
import them, so it cannot accrue app knowledge by accident, and swapping
the primitive layer for a native one later does not have to untangle
these four files first.

The package's dependencies are @app/core, @app/ui and lucide-react, and
that list is the boundary rather than a docs paragraph about it. It
imports @app/ui by subpath rather than through its barrel: user-panel
needs five primitives, and a barrel import would pull all nineteen into
the client graph of everything that renders it.

Six app imports are rewritten here rather than in a follow-up commit
because there is no way to defer them: an exports target cannot point
outside its own package, so once layout/ leaves packages/ui the
@app/ui/layout/* specifiers are dead with no shim available. The
transitional export entry added in the previous commit is removed for the
same reason. next is also dropped from @app/ui's peer dependencies --
after this move nothing in that package imports it.

The @source line in each portal's globals.css is the part with no safety
net. Tailwind scans filesystem paths, not package graphs, so a missing
entry costs nothing at type-check or build time and simply renders the
sidebar unstyled."
```

---

## Task 4: Promote `SettingsDialog` behind a footer slot

**Files:**
- Create: `web-app/packages/components/src/settings/settings-dialog.tsx`
- Delete: `web-app/apps/{internal,supplier}-portal/src/components/settings/settings-dialog.tsx`
- Modify: both portals' `src/app/(dashboard|portal)/layout.tsx`

**Interfaces:**
- Consumes: `@app/ui/dialog`, `@app/ui/button`, `@app/ui/separator`, `@app/ui/sidebar`.
- Produces: `@app/components/settings/settings-dialog` → `SettingsDialog({ sections: SettingsSection[], trigger?: React.ReactElement, footerSlot?: React.ReactNode })` and `interface SettingsSection { id: string; label: string; icon: React.ReactNode; content: React.ReactNode }`. **The `sections`/`SettingsSection` naming is renamed in Task 5** — later tasks should read Task 5's Interfaces block, not this one.

- [ ] **Step 1: Confirm the two app copies really are identical before collapsing them**

```bash
cd web-app
diff apps/internal-portal/src/components/settings/settings-dialog.tsx \
     apps/supplier-portal/src/components/settings/settings-dialog.tsx
```

Expected: no output. If there is any, stop — the divergence is information this plan does not have.

- [ ] **Step 2: Move one copy into the package and delete the other**

```bash
cd web-app
mkdir -p packages/components/src/settings
git mv apps/internal-portal/src/components/settings/settings-dialog.tsx \
       packages/components/src/settings/settings-dialog.tsx
git rm apps/supplier-portal/src/components/settings/settings-dialog.tsx
```

Nothing else needs registering. The package's `exports` is a single `"./*"` wildcard whose `*` spans `/`, its tsconfig includes `**/*.tsx` from the package root, its ESLint config has no `files` scoping, and the `@source` line names the directory and globs recursively — so a new `src/settings/` is covered by all four with no edit.

- [ ] **Step 3: Replace the hardcoded footer with a slot**

One line held this component in the apps: a hardcoded `<ServerHealthIndicator />` in its footer. That indicator reaches `@app/api-client` through `useServerStatus()`, so it cannot follow the dialog into the package.

In `web-app/packages/components/src/settings/settings-dialog.tsx`, delete the import:

```diff
-import { ServerHealthIndicator } from "./server-status"
```

add the prop to the interface:

```diff
 interface SettingsDialogProps {
   sections: SettingsSection[]
   trigger?: React.ReactElement
+  footerSlot?: React.ReactNode
 }
```

widen the destructuring:

```diff
-export function SettingsDialog({ sections, trigger }: SettingsDialogProps) {
+export function SettingsDialog({
+  sections,
+  trigger,
+  footerSlot,
+}: SettingsDialogProps) {
```

and render the slot instead of the indicator:

```diff
-            <SidebarFooter>
-              <ServerHealthIndicator />
-            </SidebarFooter>
+            {footerSlot && <SidebarFooter>{footerSlot}</SidebarFooter>}
```

This is the same seam `AppSidebar` already uses for `settingsSlot` and `userSlot`.

- [ ] **Step 4: Rewire both portals**

In **both** `apps/internal-portal/src/app/(dashboard)/layout.tsx` and `apps/supplier-portal/src/app/(portal)/layout.tsx`:

```diff
-import { SettingsDialog } from "@/components/settings/settings-dialog"
+import { SettingsDialog } from "@app/components/settings/settings-dialog"
 import { GeneralSection } from "@/components/settings/sections/general-section"
+import { ServerHealthIndicator } from "@/components/settings/server-status"
 import { ClerkUserPanel } from "@/components/layout/clerk-user-panel"
```

and pass the slot, after the `trigger` prop:

```diff
               </SidebarMenuButton>
             }
+            footerSlot={<ServerHealthIndicator />}
           />
         }
```

- [ ] **Step 5: Verify and commit**

```bash
cd web-app && pnpm type-check && pnpm build
make check-web
```

Then confirm the dialog's geometry survived the move — these classes now come from a different package, so Tailwind has to have scanned the new location:

```bash
cd web-app
grep -c "h-125" apps/internal-portal/.next/static/css/*.css    # expect non-zero
grep -c "h-125" apps/supplier-portal/.next/static/css/*.css    # expect non-zero
```

Run the portal-parity loop — still exactly three `DIFFERS:` lines.

```bash
git add -A
git commit -m "refactor(web): promote SettingsDialog behind a footer slot

The dialog was already shared chrome, and both portals carried a
byte-identical copy of it. A fork configures it through \`sections\` and
\`trigger\` without editing the body.

One line held it in the apps: a hardcoded <ServerHealthIndicator /> in
its footer. That indicator reaches @app/api-client through
useServerStatus(), so it cannot follow the dialog into the package; it
becomes a slot instead, the same seam AppSidebar already uses for
settingsSlot and userSlot.

Nothing else needed registering. The package's exports is a single \"./*\"
wildcard whose * spans \"/\", its tsconfig includes **/*.tsx from the
package root, its eslint config has no files scoping, and the @source
line in each portal's globals.css names the directory and globs
recursively -- so a new src/settings/ is covered by all four with no
edit. Verified on a clean build: h-125 and max-w-2xl!, which exist
nowhere else in the repo and set the dialog's whole geometry, are still
in both portals' emitted CSS."
```

---

## Task 5: Rename the settings tab descriptor and the general settings

**Files:**
- Modify: `web-app/packages/components/src/settings/settings-dialog.tsx`
- Rename: both portals' `src/components/settings/sections/general-section.tsx` → `src/components/settings/general-settings.tsx`
- Modify: both portals' `src/app/(dashboard|portal)/layout.tsx`

**Interfaces:**
- Consumes: `@app/components/settings/settings-dialog` as created in Task 4.
- Produces: `@app/components/settings/settings-dialog` → `SettingsDialog({ tabs: SettingsTab[], trigger?: React.ReactElement, footerSlot?: React.ReactNode })` and `interface SettingsTab { id: string; label: string; icon: React.ReactNode; content: React.ReactNode }`. Each portal exports `GeneralSettings()` from `@/components/settings/general-settings`.

"Section" currently means three things across two files: `SettingSection` (the `@app/ui` primitive), `SettingsSection` (the `{id,label,icon,content}` descriptor) and `GeneralSection` (the content one descriptor points at). Only the first is a section. The descriptor renders a left-rail entry, so it is a **tab**; the content is the General tab's **settings**.

- [ ] **Step 1: Rename the descriptor in the package**

In `web-app/packages/components/src/settings/settings-dialog.tsx`:

```diff
-export interface SettingsSection {
+export interface SettingsTab {
   id: string
   label: string
   icon: React.ReactNode
   content: React.ReactNode
 }
 
 interface SettingsDialogProps {
-  sections: SettingsSection[]
+  tabs: SettingsTab[]
   trigger?: React.ReactElement
   footerSlot?: React.ReactNode
 }
 
 export function SettingsDialog({
-  sections,
+  tabs,
   trigger,
   footerSlot,
 }: SettingsDialogProps) {
-  const [activeSection, setActiveSection] = useState(sections[0]?.id ?? "")
-  const active = sections.find((s) => s.id === activeSection)
+  const [activeTab, setActiveTab] = useState(tabs[0]?.id ?? "")
+  const active = tabs.find((t) => t.id === activeTab)
```

and in the left-rail map:

```diff
-                {sections.map((section) => (
-                  <SidebarMenuItem key={section.id}>
+                {tabs.map((tab) => (
+                  <SidebarMenuItem key={tab.id}>
                     <SidebarMenuButton
-                      isActive={activeSection === section.id}
-                      onClick={() => setActiveSection(section.id)}
+                      isActive={activeTab === tab.id}
+                      onClick={() => setActiveTab(tab.id)}
                     >
-                      {section.icon}
-                      {section.label}
+                      {tab.icon}
+                      {tab.label}
                     </SidebarMenuButton>
                   </SidebarMenuItem>
                 ))}
```

- [ ] **Step 2: Rename the content component and its file, in both portals**

```bash
cd web-app
git mv apps/internal-portal/src/components/settings/sections/general-section.tsx \
       apps/internal-portal/src/components/settings/general-settings.tsx
git mv apps/supplier-portal/src/components/settings/sections/general-section.tsx \
       apps/supplier-portal/src/components/settings/general-settings.tsx
rmdir apps/internal-portal/src/components/settings/sections \
      apps/supplier-portal/src/components/settings/sections
perl -pi -e 's{export function GeneralSection\(\)}{export function GeneralSettings()}' \
  apps/*/src/components/settings/general-settings.tsx
```

The `sections/` directory held one file and disappears with it.

- [ ] **Step 3: Fix the group heading**

In **both** `apps/*/src/components/settings/general-settings.tsx`:

```diff
-      <SettingSection title="Aspect">
+      <SettingSection title="Appearance">
```

"Aspect" reads as a carry-over from *aspetto*; the English convention for this setting is "Appearance". This is the plan's one user-visible change.

- [ ] **Step 4: Update both layouts, and type the literal**

In **both** `apps/internal-portal/src/app/(dashboard)/layout.tsx` and `apps/supplier-portal/src/app/(portal)/layout.tsx`:

```diff
-import { SettingsDialog } from "@app/components/settings/settings-dialog"
-import { GeneralSection } from "@/components/settings/sections/general-section"
+import {
+  SettingsDialog,
+  type SettingsTab,
+} from "@app/components/settings/settings-dialog"
+import { GeneralSettings } from "@/components/settings/general-settings"
```

```diff
-const SETTINGS_SECTIONS = [
+const SETTINGS_TABS: SettingsTab[] = [
   {
     id: "general",
     label: "General",
     icon: <Settings className="w-5 h-5" />,
-    content: <GeneralSection />,
+    content: <GeneralSettings />,
   },
 ]
```

```diff
           <SettingsDialog
-            sections={SETTINGS_SECTIONS}
+            tabs={SETTINGS_TABS}
```

`SettingsSection` was exported and never imported, which left the literal untyped and checked only structurally at the prop site. Annotating it `SettingsTab[]` moves a malformed entry's error to the entry.

- [ ] **Step 5: Verify and commit**

```bash
git grep -n "SettingsSection\|GeneralSection\|SETTINGS_SECTIONS\|settings/sections"
```

Expected: no output outside `docs/superpowers/`.

```bash
cd web-app && pnpm type-check && pnpm build
make check-web
```

Run the portal-parity loop — still exactly three `DIFFERS:` lines.

```bash
git add -A
git commit -m "refactor(web): rename the settings tab descriptor and general settings

\"Section\" meant three things across two files: SettingSection (the @app/ui
primitive), SettingsSection (the {id,label,icon,content} descriptor) and
GeneralSection (the content one descriptor points at). Only the first is a
section. The descriptor renders a left-rail entry, so it is a tab; the
content is the General tab's settings.

SettingsSection was exported and never imported, which left
SETTINGS_SECTIONS an untyped literal checked only structurally at the prop
site. Annotating it SettingsTab[] moves a malformed entry's error to the
entry.

\"Aspect\" as a group heading reads as a carry-over from \"aspetto\"; the
English convention for this setting is \"Appearance\"."
```

---

## Task 6: Move the shared data infrastructure into `@app/api-client`

**Files:**
- Move: `web-app/apps/internal-portal/src/hooks/use-server-status.ts` → `web-app/packages/api-client/src/use-server-status.ts`; `web-app/apps/internal-portal/src/providers/query-provider.tsx` → `web-app/packages/api-client/src/query-provider.tsx`
- Delete: the supplier portal's copies of both
- Modify: `web-app/packages/api-client/package.json`, both portals' `package.json`, `src/app/layout.tsx`, `src/components/settings/server-status.tsx`

**Interfaces:**
- Consumes: `@app/core/lib/env` → `isDevelopment`; `@app/core/constants/messages` → `messages` (both from Task 1).
- Produces: `@app/api-client/use-server-status` → `useServerStatus(): { status: GetReadinessResponse | undefined, isLoading: boolean, error: unknown }`; `@app/api-client/query-provider` → `QueryProvider({ children }: { children: React.ReactNode })`.

Both modules are infrastructure for the one server both portals call, and both are already tightly coupled to this package: `use-server-status` exists to recover a 503 body out of `ApiError`, and it relies on the `meta.silentError` convention that `query-provider` implements. Splitting them across three files in two apps is what makes that pairing invisible.

- [ ] **Step 1: Confirm the copies are identical**

```bash
cd web-app
diff apps/internal-portal/src/hooks/use-server-status.ts \
     apps/supplier-portal/src/hooks/use-server-status.ts
diff apps/internal-portal/src/providers/query-provider.tsx \
     apps/supplier-portal/src/providers/query-provider.tsx
```

Expected: no output from either.

- [ ] **Step 2: Move them**

```bash
cd web-app
git mv apps/internal-portal/src/hooks/use-server-status.ts \
       packages/api-client/src/use-server-status.ts
git mv apps/internal-portal/src/providers/query-provider.tsx \
       packages/api-client/src/query-provider.tsx
git rm apps/supplier-portal/src/hooks/use-server-status.ts
git rm apps/supplier-portal/src/providers/query-provider.tsx
rmdir apps/internal-portal/src/hooks apps/internal-portal/src/providers \
      apps/supplier-portal/src/hooks apps/supplier-portal/src/providers
```

Hand-written files are safe here: orval's `clean: true` is scoped to `src/generated/{endpoints,types,zod}` (`packages/api-client/orval.config.ts`), and `src/errors.ts`, `src/use-api-fetch.ts` and `src/index.ts` already live alongside it. `make gen-contract` will not touch them.

- [ ] **Step 3: Rewrite their imports to be package-local**

In `web-app/packages/api-client/src/use-server-status.ts`:

```diff
-import { ApiError } from "@app/api-client"
-import { useGetReadiness } from "@app/api-client/endpoints/system"
-import { GetReadinessResponse } from "@app/api-client/zod/system"
+import { ApiError } from "./errors"
+import { useGetReadiness } from "./generated/endpoints/system"
+import { GetReadinessResponse } from "./generated/zod/system"
```

A package importing itself by name would resolve through its own `exports` map, which works but makes the module look like a consumer of a package it is part of.

In `web-app/packages/api-client/src/query-provider.tsx`, one line changes:

```diff
-import { ApiError } from "@app/api-client"
+import { ApiError } from "./errors"
```

Its two `@app/core` specifiers were already rewritten in Task 1 and stay as they are.

- [ ] **Step 4: Declare the new dependencies and exports**

In `web-app/packages/api-client/package.json`, add to `exports`:

```json
    "./use-server-status": "./src/use-server-status.ts",
    "./query-provider": "./src/query-provider.tsx",
```

and to `dependencies`:

```json
    "@app/core": "workspace:*",
    "@tanstack/react-query-devtools": "^5.97.0",
    "sonner": "^2.0.0",
```

`sonner` and the devtools follow `query-provider` in. `@app/core` supplies `messages` and `isDevelopment`.

This package must **not** gain `@app/ui` or `@app/components` — it sits below them, and `@app/auth` already depends on nothing above itself.

- [ ] **Step 5: Rewire both portals**

In **both** `apps/*/src/app/layout.tsx`:

```diff
-import { QueryProvider } from "@/providers/query-provider"
+import { QueryProvider } from "@app/api-client/query-provider"
```

In **both** `apps/*/src/components/settings/server-status.tsx`:

```diff
-import { useServerStatus } from "@/hooks/use-server-status"
+import { useServerStatus } from "@app/api-client/use-server-status"
```

Then drop `"@tanstack/react-query-devtools"` and `"sonner"` from **both** apps' `package.json` — after this move neither app imports either. `@tanstack/react-query` stays: both apps still need the peer for `QueryClientProvider` to share a React context.

Check the exact import specifier in each `layout.tsx` before running a blind substitution — it may be a relative path rather than the `@/` alias:

```bash
cd web-app && grep -n "query-provider" apps/*/src/app/layout.tsx
```

- [ ] **Step 6: Verify and commit**

```bash
git grep -n "@/hooks/use-server-status\|@/providers/query-provider"
```

Expected: no output.

```bash
cd web-app && pnpm install && pnpm type-check && pnpm build
make check-web
```

Then confirm the generated client is untouched by the move:

```bash
make check-contract
```

Expected: PASS — it regenerates and fails on any drift, which is the direct test that hand-written siblings do not confuse orval.

Run the portal-parity loop — `app/layout.tsx` was already one of the three expected `DIFFERS:` lines, so the output is unchanged.

```bash
git add -A
git commit -m "refactor(api-client): absorb the shared query provider and readiness hook

Both portals carried byte-identical copies of useServerStatus and
QueryProvider. Neither is portal-specific: they are infrastructure for the
one FastAPI server both portals call, and both are already tightly coupled
to this package. useServerStatus exists to recover a 503 body out of
ApiError, and it depends on the meta.silentError convention QueryProvider
implements -- a pairing that was invisible while the two lived in
different directories in different apps.

Hand-written files are safe here: orval's clean: true is scoped to
src/generated/{endpoints,types,zod}, and errors.ts, use-api-fetch.ts and
index.ts already sit alongside it. make check-contract passes, which is
the direct test.

Both modules now import ./errors rather than @app/api-client. A package
importing itself by name resolves through its own exports map, which works
but makes the module look like a consumer of a package it is part of.

sonner and the react-query devtools follow QueryProvider in and come out
of both apps. @tanstack/react-query stays in the apps: QueryClientProvider
needs a single shared React context."
```

---

## Task 7: Split `ServerHealthIndicator` into a shared view and a thin wiring wrapper

**Files:**
- Create: `web-app/packages/components/src/settings/server-status-indicator.tsx`
- Rewrite: both portals' `src/components/settings/server-status.tsx`

**Interfaces:**
- Consumes: `@app/api-client/use-server-status` → `useServerStatus()` (Task 6); `@app/core/lib/env` → `isDevelopment` (Task 1); `@app/core/lib/utils` → `cn` (Task 1); `@app/ui/hover-card`, `@app/ui/badge`.
- Produces: `@app/components/settings/server-status-indicator` → `ServerStatusIndicator({ status?: ServerStatus, isLoading: boolean, error: unknown, showDetail?: boolean })`. Each portal keeps `ServerHealthIndicator()` at `@/components/settings/server-status`, unchanged in name and call signature, so Task 4's `footerSlot={<ServerHealthIndicator />}` still compiles.

`ServerHealthIndicator` is ~140 identical lines of `HoverCard` markup whose only impurities are one `useServerStatus()` call and one module-load `isDevelopment` read. Pushing both up into a thin app wrapper is the same move `footerSlot` makes, one level deeper. `@app/components` may not import `@app/api-client`, so the `status` shape is declared structurally.

- [ ] **Step 1: Create the presentational component**

```bash
cd web-app
git mv apps/internal-portal/src/components/settings/server-status.tsx \
       packages/components/src/settings/server-status-indicator.tsx
```

Then, in `web-app/packages/components/src/settings/server-status-indicator.tsx`, replace the import block and the function signature. Imports become:

```tsx
"use client"

import { cn } from "@app/core/lib/utils"
import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from "@app/ui/hover-card"
import { Badge } from "@app/ui/badge"
```

Then insert the prop types immediately below, and change the signature:

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
  /** Show the hover-card breakdown. Hoisted from a module-load env read so
      the component renders both branches under test. */
  showDetail?: boolean
}

export function ServerStatusIndicator({
  status,
  isLoading,
  error,
  showDetail = false,
}: ServerStatusIndicatorProps) {
```

Delete the old first line of the body:

```diff
-  const { status, isLoading, error } = useServerStatus()
```

and change the development gate near the end from a module-load constant to the prop:

```diff
-  if (!isDevelopment) {
+  if (!showDetail) {
     return statusIndicator
   }
```

Everything between — the `isLoading` early return, `statusColor`, `statusIndicator`, and the whole `HoverCard` block — is unchanged.

- [ ] **Step 2: Write the wiring wrapper in the internal portal**

Create `web-app/apps/internal-portal/src/components/settings/server-status.tsx`:

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

- [ ] **Step 3: Write the identical wrapper in the supplier portal**

Overwrite `web-app/apps/supplier-portal/src/components/settings/server-status.tsx` with **exactly** the same content as Step 2 — these two files must stay byte-identical.

```bash
cd web-app
cp apps/internal-portal/src/components/settings/server-status.tsx \
   apps/supplier-portal/src/components/settings/server-status.tsx
diff apps/internal-portal/src/components/settings/server-status.tsx \
     apps/supplier-portal/src/components/settings/server-status.tsx
```

Expected: no output from the diff.

- [ ] **Step 4: Verify the boundary held**

```bash
grep -n "api-client\|clerk" web-app/packages/components/package.json
```

Expected: no output. The dependency list is still `@app/core`, `@app/ui`, `lucide-react`.

```bash
grep -rn "@app/api-client\|@clerk" web-app/packages/components/src
```

Expected: no output.

- [ ] **Step 5: Verify and commit**

```bash
cd web-app && pnpm type-check && pnpm build
make check-web
```

Then confirm the widget's classes are still emitted from their new location:

```bash
cd web-app
grep -c "animate-ping" apps/internal-portal/.next/static/css/*.css   # expect non-zero
grep -c "animate-ping" apps/supplier-portal/.next/static/css/*.css   # expect non-zero
```

Run the portal-parity loop — still exactly three `DIFFERS:` lines.

```bash
git add -A
git commit -m "refactor(web): share the server health widget, keep its wiring per portal

ServerHealthIndicator was ~140 byte-identical lines in each portal whose
only impurities were one useServerStatus() call and one module-load
isDevelopment read. The markup moves into @app/components; each portal
keeps a twelve-line wrapper that makes the hook call and passes the result
down. This is the same move footerSlot makes, one level deeper.

@app/components must not depend on @app/api-client, so the status prop is
declared structurally rather than imported -- the generated
GetReadinessResponse is assignable to it, so the app wrapper passes the
real value with no cast.

Hoisting isDevelopment to a showDetail prop is not only what keeps the
component pure. A module-load environment read makes a passing test cover
half its component, because the branch it selects is fixed before the test
can choose."
```

---

## Task 8: Update the documentation

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `web-app/CLAUDE.md`, `web-app/README.md`, `docs/setup/making-it-yours.md`, `web-app/apps/internal-portal/README.md`, `web-app/apps/supplier-portal/README.md`

**Interfaces:**
- Consumes: the final tree from Tasks 1–7.
- Produces: nothing code-facing.

- [ ] **Step 1: Find every stale path reference**

```bash
cd /path/to/repo/root
grep -rn "packages/ui\|@app/ui\|components/ui\|general-section\|SettingsSection" \
  --include="*.md" . | grep -v node_modules | grep -v "docs/superpowers/"
```

Work through every hit. `docs/superpowers/plans/` and `docs/superpowers/specs/` are historical records — a plan describes what was true when it was written — and are **left alone**.

- [ ] **Step 2: Update the three workspace trees**

`CLAUDE.md:29`, in the repo-structure block:

```diff
 │       ├── auth/              # @app/auth — Role enum, useAppAuth(), getUserRole()
-│       └── ui/                # @app/ui — shared component library (shadcn/ui)
+│       ├── core/              # @app/core — cn(), NavItem, copy — no renderer
+│       ├── ui/                # @app/ui — shadcn/Base UI primitives, WEB ONLY
+│       └── components/        # @app/components — composed chrome, built on ui
```

`README.md:14` and `README.md:95`, and `web-app/CLAUDE.md:17`, take the same three-line replacement, matching each file's existing comment style.

`README.md:14` prose also needs widening:

```diff
-- **Two Next.js 16 portals** sharing `packages/ui`, `packages/auth` and a generated
+- **Two Next.js 16 portals** sharing `packages/core`, `packages/ui`,
+  `packages/components`, `packages/auth` and a generated
```

- [ ] **Step 3: Add the section that explains why there are three**

In `web-app/CLAUDE.md`, directly under the workspace tree:

````markdown
### The three UI packages, and why they are three

They stack: `@app/core` ← `@app/ui` ← `@app/components` ← `apps/*`. The split is by
what survives a React Native port, not by taste — and by what two portals can share
without pretending they are one app.

- **`@app/core`** holds everything with no render dependency. It builds with
  `lib: ["esnext"]` and no `"dom"`, so `window` in its own source is a **type error** —
  that is the enforcement, not a convention. `skipLibCheck` is load-bearing alongside it
  (see the comment in its tsconfig); do not flip it off.
- **`@app/ui`** is web-only and permanently so. Base UI, DOM elements, CSS variables,
  `sonner` and `next-themes` do not run on React Native. A native target means a second
  primitives package, never an adapter for this one.
- **`@app/components`** is composed chrome that knows the app's nav shape, user model,
  branding and settings surface. It reaches for `next/image`, `next/link` and
  `usePathname`.

**`@app/components` depends on `@app/core`, `@app/ui` and `lucide-react` — and nothing
else, ever.** Its `package.json` is the boundary; a docs paragraph is not. Shared code
that needs Clerk or the API client does not go there. It goes into the package it is
already coupled to (`@app/api-client` holds `useServerStatus` and `QueryProvider`), or
it stays in each portal.

Import shapes differ on purpose — the subpath should carry information:

```ts
import { Button, Skeleton } from "@app/ui"                          // barrel
import { Skeleton } from "@app/ui/skeleton"                         // subpaths also work
import { AppSidebar } from "@app/components/layout/app-sidebar"     // no barrel
import { cn } from "@app/core/lib/utils"                            // no barrel
import type { NavItem } from "@app/core/types/nav"
```

`@app/ui`'s `exports` is wildcard-based, so `shadcn add` needs no `package.json` edit —
but its barrel (`packages/ui/src/index.ts`) is still hand-maintained, so **a new
primitive needs a line there** or it is silently missing from `@app/ui`.

### Where a new component goes

| The component… | Goes in |
|---|---|
| has no render dependency at all | `packages/core` |
| is a shadcn/Base UI primitive | `packages/ui` |
| composes primitives, no Clerk and no API client | `packages/components` |
| is shared by both portals and needs the API client | `packages/api-client` |
| is bound to **one portal's** auth, routes or payloads | that portal's `src/components/` |
| is a shipped example a fork should **rewrite, not configure** | that portal's `src/components/`, even with no such binding |

The last row is what `general-settings.tsx` is. It imports only `@app/ui` and
`next-themes`, so the rule above says "promote" — and it stays in both portals anyway.
Its body *is* the customization, `SETTINGS_TABS` is the extension point it hangs off,
and duplicating it is the demonstration that each portal owns its settings surface. The
question that decides this row is: **does a fork configure this, or rewrite it?**

The slot pattern (`settingsSlot`, `userSlot`, `footerSlot`) is the promotion mechanism,
not just a way to avoid importing `@app/auth` into `packages/components`. When one
impure line is all that holds a component in an app, the line becomes a slot and the
component moves up.

### Failure modes with no safety net

- A new package without a matching `@source` line in **both** portals' `globals.css`
  builds clean and renders unstyled. Tailwind scans filesystem paths, not package
  graphs. Verify against `h-125` and `max-w-2xl!` in the emitted CSS — they exist
  nowhere else in the repo.
- A new primitive is importable as `@app/ui/<name>` immediately, because `exports` is a
  wildcard, but is missing from the barrel until someone edits `src/index.ts` by hand.
  That has already happened twice — `AvatarBadge` and `SidebarFooterMenu`.
- `packages/core` compiles without the `dom` lib, so the "no renderer" rule is enforced
  by `tsc` rather than by review. Worth stating, because the error it produces looks
  like a misconfiguration if you do not know it is deliberate.
- A new workspace package needs its `package.json` copied in `web-app/Dockerfile`'s
  deps stage, or `pnpm install --frozen-lockfile` fails in the container and nowhere
  else.
````

- [ ] **Step 4: Fix the dependency and shadcn guidance**

`web-app/README.md:63-69`, the "Where to add a dependency" table:

```diff
 | Dependency type | Where to add |
 |-----------------|--------------|
 | Runtime dep used by one portal | that portal's `apps/` directory |
-| Pure UI wrapper / zero-config provider | `packages/ui` |
+| Needed by a primitive | `packages/ui` |
+| Needed by composed chrome | `packages/components` |
+| Pure helper, type or constant — no rendering | `packages/core` |
 | Tooling (eslint, typescript, etc.) | Workspace root (`-w`) |
```

`web-app/README.md:88-94`, the shadcn workflow — the generated path changed:

```diff
-Components land in `packages/ui/src/components/ui/` and are exported from `packages/ui/src/index.ts`. Import them in apps via `@app/ui`.
+Components land in `packages/ui/src/primitives/` and are importable as `@app/ui/<name>`
+immediately — the `exports` map is a wildcard. They are **not** in the `@app/ui` barrel
+until you add a line to `packages/ui/src/index.ts` by hand.
```

`web-app/CLAUDE.md:120` and `:237` currently send the reader to `packages/ui` for any new component. Point them at the placement table from Step 3 instead. `:246` ("Putting auth logic in `packages/ui`") stays true and needs no edit.

- [ ] **Step 5: Fix the three `company-logo.tsx` path references**

`docs/setup/making-it-yours.md:66`, `web-app/apps/internal-portal/README.md:122` and `web-app/apps/supplier-portal/README.md:124`:

```diff
-`packages/ui/src/components/layout/company-logo.tsx`
+`packages/components/src/layout/company-logo.tsx`
```

In both portal READMEs, `:147` and `:151` (supplier: `:151` and `:155`) describe `@app/ui` as "shared shadcn/ui components" and say "Always check `packages/ui` before creating new components" — update both to name all three packages and point at the placement table.

In `docs/setup/making-it-yours.md`, the frontend-identity table gains a row and one moves:

```diff
 | Sidebar nav items | `src/lib/hub-nav.ts` → `HUB_NAV` |
+| Error toast copy | `web-app/packages/core/src/constants/messages.ts` → `messages.toasts` |
+| Settings tabs | `src/app/(dashboard)/layout.tsx` → `SETTINGS_TABS` |
```

- [ ] **Step 6: Verify and commit**

```bash
cd /path/to/repo/root
grep -rn "packages/ui/src/components\|general-section\|SettingsSection\|SETTINGS_SECTIONS" \
  --include="*.md" . | grep -v node_modules | grep -v "docs/superpowers/"
```

Expected: no output.

Then confirm every path named in the docs actually exists:

```bash
grep -rhno "packages/[a-z-]*/src/[a-z/.-]*" --include="*.md" . \
  | grep -v node_modules | cut -d: -f2 | sort -u \
  | while read p; do [ -e "web-app/$p" ] || echo "STALE: $p"; done
```

Expected: no output.

```bash
git add -A
git commit -m "docs: describe the three-package split and the traps in it

Updates the package trees in CLAUDE.md, web-app/CLAUDE.md and all four
READMEs, and rewrites the guidance that would otherwise send the next
contributor to a path that no longer exists -- the shadcn workflow in
web-app/README.md still named packages/ui/src/components/ui/, and
company-logo.tsx is referenced by path in three places.

The additions worth having are the failure modes, all of which are silent:

- A new package without a matching @source line in BOTH portals'
  globals.css builds clean and renders unstyled.
- A new primitive is importable as @app/ui/<name> immediately, because
  exports is a wildcard, but is missing from the barrel until someone
  edits src/index.ts by hand. That has already happened twice.
- packages/core compiles without the dom lib, so the \"no renderer\" rule
  is enforced by tsc rather than by review. Worth stating, because the
  error it produces looks like a misconfiguration if you do not know it
  is deliberate.
- A new workspace package needs its package.json copied in the
  Dockerfile's deps stage, or --frozen-lockfile fails in the container
  and nowhere else.

Also records where a new component goes now that there are five places it
could go, why general-settings.tsx stays duplicated in both portals, and
that the slot pattern is the promotion mechanism rather than only a way
to keep @app/auth out of packages/components."
```

---

## Final verification

After Task 8, from the repo root:

- [ ] `cd web-app && pnpm install && pnpm type-check` — PASS across seven projects
- [ ] `make check-web` — ESLint and Prettier clean
- [ ] `make check-contract` — PASS (the generated client survived Task 6)
- [ ] `cd web-app && pnpm build` — both portals build
- [ ] `git grep -n "@app/ui/layout/"` — no output
- [ ] `git grep -n "components/ui/"` — no output outside `docs/superpowers/`
- [ ] The portal-parity loop prints exactly `app/layout.tsx`, `app/unauthorized/page.tsx`, `proxy.ts`
- [ ] The `window` probe from Task 1 Step 12, re-run once: still TS2304
- [ ] `docker build --target builder` for one portal reaches `✓ Compiled successfully`

**Browser check, both portals.** Start the stack and sign in to each portal:

- [ ] Internal portal (`:3000`): sidebar renders **styled**, collapses to icons, tooltips show the right label per item
- [ ] Settings dialog opens at its correct geometry (not a default-width box), server indicator in the footer, heading reads **"Appearance"**
- [ ] Theme select switches light/dark/system
- [ ] User panel signs out to `/sign-in`
- [ ] Supplier portal (`:3002`): all of the above. **This one matters** — the supplier portal's role-guard paths went unverified in the auth-fixes port, so this is the first live exercise of its chrome.

An unstyled sidebar is the signature of a missing `@source` line and is the one failure the build will not report.

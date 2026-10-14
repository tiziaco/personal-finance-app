# Components, Primitives and Packages

Where a new component goes, how Base UI primitives are used and added, and what a new workspace
package needs. The package stack and why it is split three ways are in
`docs/architecture/web-app.md` §1. Paths below are relative to `web-app/`.

Placement is enforced by review, except in two places: each package's `package.json` is the list of
what it may import, and `packages/core` compiles without the `dom` lib. Everything else in the last
section fails somewhere other than where the edit is missing.

## Where a component goes

| The component… | Goes in |
|---|---|
| has no render dependency at all | `packages/core` |
| is a shadcn/Base UI primitive | `packages/ui` |
| is generic table, filter or list-state machinery — no domain, no API client | `packages/data-table` |
| composes primitives, no Clerk and no API client | `packages/components` |
| is shared and needs the API client | `packages/api-client` |
| is bound to the app's auth, routes or payloads | `apps/web/src/components/` |
| is a shipped example a fork should **rewrite, not configure** | `apps/web/src/components/`, even with no such binding |

Take the first row that matches. The last row is `general-settings.tsx`: it imports only `@app/ui`,
`next-themes` and `lucide-react`, so the table says "promote", and it stays in the app anyway. Its
body *is* the customization — `SETTINGS_TABS`, defined inline in the route-group layout, is the
extension point it hangs off. The question that decides the row: **does a fork configure this, or
rewrite it?**

`packages/components` depends on `@app/core`, `@app/ui` and `lucide-react` — and nothing else, ever.
Shared code that needs Clerk or the API client goes into the package it is already coupled to
(`@app/api-client` holds `useServerStatus` and `QueryProvider`), or stays in the app.

## Slots move a component up

When one impure line is all that holds a component in an app, that line becomes a slot and the
component moves to `packages/components`. The existing slots:

| Component | Slot | Filled by |
|---|---|---|
| `AppSidebar` (`layout/app-sidebar.tsx`) | `settingsSlot`, `userSlot` | `<SettingsDialog …>`, `<ClerkUserPanel />` |
| `SettingsDialog` (`settings/settings-dialog.tsx`) | `footerSlot` | `<ServerHealthIndicator />` |

Both are filled in `apps/web/src/app/(dashboard)/layout.tsx`. A slot is a `ReactNode` prop, rendered where the impure piece was.

## Using Base UI

The primitives are Base UI (`@base-ui/react`), not Radix. Generic shadcn examples are Radix and are
wrong here:

```tsx
// ✅ Base UI — the trigger renders as the element you pass
<DropdownMenuTrigger render={<SidebarMenuButton size="lg" />}>…</DropdownMenuTrigger>

// ❌ Radix — asChild does not exist here
<DropdownMenuTrigger asChild><Button>…</Button></DropdownMenuTrigger>
```

- `DropdownMenuLabel` must be inside a `DropdownMenuGroup`.
- A trigger that is already a `<button>` takes the styling directly (`className={cn(badgeVariants(), …)}`)
  rather than wrapping another button.
- Worked example of both: `packages/components/src/layout/user-panel.tsx` (the trigger, then two
  `DropdownMenuGroup`s).

Import by subpath — `import { Button } from "@app/ui/button"`. The barrel `@app/ui` pulls every
primitive into the client graph; nothing in the repo imports it. `@app/components/<dir>/<file>` and
`@app/core/<dir>/<file>` have no barrel at all.

## Adding a primitive

Every primitive goes in `packages/ui`, even one only a single screen uses.

1. Install it by hand from the shadcn docs (`ui.shadcn.com/docs/components/base/<name>`, the **Manual**
   tab — the Base UI variant, never the Radix one): its dependencies go in `packages/ui/package.json`,
   its code in `src/primitives/<name>.tsx`. Point the `cn` import at `@app/core/lib/utils`. The
   `shadcn` CLI is not used — it cannot resolve that alias.
2. It is importable as `@app/ui/<name>` immediately — `exports` is a wildcard.
3. **Add its exports to the barrel, `packages/ui/src/index.ts`, by hand.** Nothing fails without it; the
   primitive is just silently missing from `@app/ui`. This has been missed twice (`AvatarBadge`,
   `SidebarFooterMenu`).
4. `pnpm exec prettier --write` the new file — the docs' code is not in the repo's style.
5. **Bring its corners to the radius scale below.** shadcn's styles disagree — `base-maia` pills
   (`rounded-4xl`) next to `base-mira`'s `rounded-lg` — and the primitives came from both.

### Corner radius

Three levels, by what the element is. `--radius` is 10px (`lg`); the tokens are in `globals.css`.

| Element | Radius |
|---|---|
| A control — button (every size), input, textarea, select trigger, sidebar menu button | `rounded-lg` |
| A floating list — popover, select and dropdown content, hover card | `rounded-lg`, its items `rounded-md` |
| A surface — dialog, alert dialog, card, the table frame, the bulk-action pill | `rounded-xl` |
| A badge or a filter chip | `rounded-md` |
| Round by nature — avatar, switch, status dot, a count bubble | `rounded-full` |

An item inside a list is one step smaller than the list, so the two corners nest.

## Adding a workspace package

A new `packages/<name>` builds and type-checks with none of these, and then fails far away:

| Edit | Missing, it fails as… |
|---|---|
| `@source "../../../../packages/<name>/src";` in **both** `apps/*/src/styles/globals.css` | a clean build that renders unstyled — Tailwind scans paths, not the package graph. Check the emitted CSS for a class used only in that package |
| the package in `transpilePackages` in **both** `apps/*/next.config.ts` | a parse error inside the package's raw TypeScript, pointing nowhere near the config |
| `COPY packages/<name>/package.json ./packages/<name>/` in `Dockerfile`'s deps stage | `pnpm install --frozen-lockfile` failing in the container only |
| a `"lint": "eslint"` script and an `eslint.config.mjs` | nothing — the root `lint` is `pnpm -r --if-present`, so the package is never linted, and no CI runs web checks |

Its tests need no config: the `packages` project in `vitest.config.mts` globs `packages/*/src`.

A `window` or `document` reference in `packages/core` is a type error by design — it builds with
`lib: ["esnext"]` and no `dom`. `skipLibCheck` in its tsconfig is load-bearing alongside that; leave it.

## Verify

- The component's imports respect its package's `package.json` dependencies.
- A new primitive has its barrel line; a new package has all three edits above.
- `make check-web` from the repo root.

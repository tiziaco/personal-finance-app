---
name: web-app-testing
description: >
  Writing, running and debugging tests in the Next.js workspace (Vitest + Testing Library in jsdom).
  Use when adding or changing a test under web-app/, deciding whether a component needs one,
  debugging a test that fails for no obvious reason or passes while covering nothing, touching
  vitest.config.mts or vitest.setup.ts, adding a third app, or hitting a type-check error that only
  appears in a test file. Trigger on "write a test for X", "add tests", "this test fails",
  "matchMedia is not a function", "useSidebar must be used within a SidebarProvider", "does this
  need a test", or any work on *.test.ts(x) under web-app/.
---

# Web App Testing

Vitest + Testing Library in jsdom. One config, `web-app/vitest.config.mts`, three projects:

| Project | Runs | `@/` |
|---|---|---|
| `packages` | `packages/*/src/**/*.test.*` | — |
| `internal-portal` | `apps/internal-portal/src/**/*.test.*` | that app's `src/` |
| `supplier-portal` | `apps/supplier-portal/src/**/*.test.*` | that app's `src/` |

```bash
pnpm test                          # from web-app/, once
pnpm test --project packages       # one project
pnpm test packages/auth            # one path
pnpm test:watch
make test-web                      # from the repo root; also what pre-push runs
```

## Does it earn a test?

Ask whether it has a **branch** or is a pass-through. `packages/ui/src/primitives/` is vendored
shadcn — testing it tests Base UI. What earns a test is a condition, state, or a mapping:
`getUserRole`'s prefix rule, `AuthProvider`'s `AppUser` mapping and `signOut` ordering,
`useServerStatus`'s 503 recovery, `UserDetailsPanel`'s optional items, `ClerkUserPanel`'s PM-only
Organisation item.

A test written after its subject proves nothing until it has failed once: break the branch it
pins, watch it go red, revert.

## Traps

### 1. Sidebar primitives need a `SidebarProvider` — and it needs `matchMedia`

Every export of `packages/ui/src/primitives/sidebar.tsx` calls `useSidebar()`, which throws outside
a `SidebarProvider` — including `Sidebar collapsible="none"`. `UserDetailsPanel` calls it directly;
`SettingsDialog`'s tab rail is sidebar primitives borrowing the page's provider. Render them with
`render(ui, { wrapper: SidebarProvider })`. The provider calls `useIsMobile()` → `window.matchMedia`,
which jsdom lacks: `vitest.setup.ts` stubs it. Do not delete the stub.

### 2. Test files are type-checked

`pnpm type-check` and `next build` compile them like source:

- A `.catch((e) => e)` is `unknown` and fails the build. Use `await expect(p).rejects…` or a
  `try/catch` that narrows.
- jest-dom's matchers (`toBeInTheDocument`, …) need a `src/testing.d.ts` importing
  `@testing-library/jest-dom/vitest` in **each** package or app that uses them —
  `vitest.setup.ts` belongs to no tsconfig. `components` and both portals have one; add it to a new
  package the first time it uses a matcher.

### 3. `NODE_ENV` is pinned in `vitest.config.mts`

Vitest defaults it only when unset, and the root Makefile exports
`apps/internal-portal/.env.local` wholesale. Under `NODE_ENV=production` React loads its production
build and every render test fails nowhere near the cause. The pin covers every entry point. **Keep
the line**, and keep `NODE_ENV` out of env files.

### 4. The root React pin must match the portals

`web-app/package.json` pins `react` / `react-dom` to the portals' exact version, and
`resolve.dedupe` resolves every test to that root copy. Bump React in `apps/*` alone and
the tests silently run a different React than the portals ship. Bump all three together.

### 5. Module-load constants cover half a component

`isDevelopment` (`packages/core/src/lib/env.ts`) is computed once at import, so under Vitest it is
always `false`. Reassigning `process.env.NODE_ENV` mid-test changes nothing. `ServerStatusIndicator`
avoids this by taking `showDetail` as a prop, and the portal wrapper passes `isDevelopment` —
test the prop. Hoist the next such read the same way before reaching for a module mock.

## Mocking

- Mock the vendor edge, keep the logic real: `@clerk/nextjs` in `provider.test.tsx`; the generated
  query hook (not the Zod validator) in `use-server-status.test.ts`.
- Keep real exports when mocking one: `vi.mock("@app/auth", async (orig) => ({ ...(await orig()), useAppAuth: … }))`.
- Hoist mock state with `vi.hoisted` so the `vi.mock` factory can read it.
- `window.location.assign` is replaced via `Object.defineProperty(window, "location", …)`; restore it
  in `afterEach`.
- A whole-object `toEqual` only pins a field mapping if every field holds a distinguishable value.

## Conventions

- **Co-located**: `user-panel.test.tsx` next to `user-panel.tsx`, so it rides along with `git mv`.
  `@app/components` exports `./*`, so a test is nominally importable as a module; harmless, the
  package is private.
- **`*.test.*` is Vitest, `*.spec.*` is Playwright** (none yet; `e2e/**` is excluded).
- **Explicit imports**: `globals: false`, so `import { describe, it, expect, vi } from "vitest"`.
- **A third app** gets `portal("<app>")` in the config's `projects`, a `src/testing.d.ts`, and its
  own copy of any duplicated component's test.

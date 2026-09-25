# Web Test Suite (Vitest) — Design

**Status:** approved design, not yet implemented
**Branch:** `test/web-vitest`
**Ports:** [`tiziaco/flyorbit`](https://github.com/tiziaco/flyorbit)'s web test setup (`web-app/vitest.config.mts`, `vitest.setup.ts`, the `web-app-testing` skill), adapted for a workspace with two portals
**Scope:** web-app test tooling, the tests themselves, one `getUserRole` fix, the push gate and docs. No server change; `make check-contract` stays clean.

---

## Goal

`web-app/` has no test runner. The logic the portals depend on — the auth seam (`signOut`, `AppUser`, `getUserRole`), the API mutator, the server-status recovery — is verified only by type-checking and by hand. After this change:

```bash
make test-web          # from the repo root
pnpm test              # from web-app/, once
pnpm test:watch        # from web-app/, watch mode
```

run every test in the workspace, and `.githooks/pre-push` runs them whenever `web-app/` changed.

---

## Why this differs from the port

1. **Two portals, so three Vitest projects.** flyorbit's single config aliases `@/` to its one app, and its own comment says that has to become `test.projects` the day a second `@/` appears. Here there are two from day one.
2. **The sidebar trap is live here.** flyorbit's rail stopped rendering sidebar primitives, so no test needs a `SidebarProvider`. Here `UserDetailsPanel` calls `useSidebar()` and `SettingsDialog` renders `Sidebar` primitives with no provider of its own (it borrows the page's), so tests wrap both — and `SidebarProvider` → `useIsMobile()` → `window.matchMedia`, which jsdom lacks. The `matchMedia` stub is load-bearing, not defensive.
3. **The tests are rewritten, not copied.** Only `use-api-fetch.ts` matches flyorbit (one comment word differs). `permissions.ts`, `provider.tsx`, `user-panel.tsx` and `settings-dialog.tsx` differ by 55–200 lines: org roles instead of a platform claim, `AppUser` instead of no user, a PM-only organization item. `use-api-fetch.test.ts` ports verbatim; everything else is written against this repo.
4. **The suite gates pushes.** flyorbit runs it by hand only. Here the pre-push hook is the only gate for web checks — no CI runs them — and the suite is a few seconds of jsdom, so it runs there after `check-web`.
5. **`NODE_ENV=production` is still in both `.env.example` files.** flyorbit removed it from its example; the root `Makefile` `-include`s and exports `web-app/apps/internal-portal/.env.local`, so a fork copying the example would run every `make test-web` under React's production build. The config pins `NODE_ENV=test` regardless (§1), and the line is removed too.

---

## 1. Tooling

**Dependencies** — root `web-app/package.json` `devDependencies`, flyorbit's versions:
`vitest ^5.0.1`, `jsdom ^30.0.1`, `@vitejs/plugin-react ^6.1.1`, `@testing-library/react ^16.3.3`, `@testing-library/dom ^10.4.2`, `@testing-library/jest-dom ^7.0.1`, `@testing-library/user-event ^14.6.7`. Scripts: `"test": "vitest run"`, `"test:watch": "vitest"`.

The workspace root does not declare `react`/`react-dom` today (flyorbit's does). If `@testing-library/react`'s peer resolution needs them at the root, add them pinned to the apps' exact `19.2.4`, never a range, so the root cannot resolve a second copy.

**`web-app/vitest.config.mts`** — one file, three inline projects that `extends: true` the root:

| Root options (inherited) | |
|---|---|
| `process.env.NODE_ENV = "test"` | first statement, before anything reads it |
| `plugins: [react()]` | |
| `resolve.dedupe: ["react", "react-dom"]` | one React copy across per-package symlinks |
| `test.environment: "jsdom"` | |
| `test.setupFiles: ["./vitest.setup.ts"]` | |
| `test.exclude` | `node_modules`, `.next`, `dist`, `e2e/**` |
| `test.globals: false` | explicit `import { … } from "vitest"`; no `types` array in seven standalone tsconfigs |

| Project | `include` | `resolve.alias` |
|---|---|---|
| `packages` | `packages/*/src/**/*.test.?(c\|m)[jt]s?(x)` | none |
| `internal-portal` | `apps/internal-portal/src/**/*.test.?(c\|m)[jt]s?(x)` | `@/` → `apps/internal-portal/src/` |
| `supplier-portal` | `apps/supplier-portal/src/**/*.test.?(c\|m)[jt]s?(x)` | `@/` → `apps/supplier-portal/src/` |

`.test.` only: `.spec.` is reserved for Playwright. `packages/ui` declares `@/*` in its tsconfig but imports nothing through it, so the `packages` project needs no alias; if that changes, it gets one.

**`web-app/vitest.setup.ts`**: `cleanup()` after each test (Testing Library only auto-cleans with globals on); `import "@testing-library/jest-dom/vitest"`; a `window.matchMedia` stub (§ Why 2); `NEXT_PUBLIC_API_URL` defaulted, since `resolveBaseUrl()` throws when unset and Next is not there to inline it.

**`src/testing.d.ts`** — `import "@testing-library/jest-dom/vitest"` in each package/app whose tests use jest-dom matchers (`components`, both apps — the `auth` and `api-client` tests use `renderHook` and plain assertions). `pnpm type-check` covers test files, and `vitest.setup.ts` belongs to no tsconfig, so its augmentation does not reach them.

**No sidebar helper.** Tests that render sidebar primitives pass `{ wrapper: SidebarProvider }` to `render` inline. A shared helper would be that one option, and `@app/components`' wildcard `exports` would make it importable by the portals.

## 2. The `getUserRole` fix

`permissions.ts` strips with `orgRole.replace("org:", "")`: the first `org:` *anywhere*, and a value with no prefix passes through. So `getUserRole("supplier")` returns `Role.SUPPLIER`, and `getUserRole("supplierorg:")` does too. Harmless with the values Clerk sends — every org role is `org:`-prefixed — but it is the portability seam, and its contract should be exact: **only a leading `org:` is stripped, and a value without it is not a role.** The test lands first, failing; the fix makes it pass.

## 3. The tests

Co-located with their subjects.

| File | Pins |
|---|---|
| `packages/auth/src/permissions.test.ts` | `getUserRole`: each `org:` role narrows; unknown, unprefixed, mid-string prefix, wrong case → `null`; `null`/`undefined`/`""` → `null`. `isInternalRole` true for the three internal roles, false for supplier and `null`; `isSupplierRole` the inverse. `ROLE_LABELS` non-empty for every role. |
| `packages/auth/src/provider.test.tsx` | `@clerk/nextjs` mocked. `role` from `orgRole`. `user` is `AppUser`: name from first + last, one of them missing, both missing → `null`; missing email → `null`; empty `imageUrl` → `null`; no Clerk user → `null`. `signOut`: calls Clerk with `{ redirectUrl }` then `window.location.assign(signOutUrl)`; still assigns when Clerk rejects; defaults to `"/"`. |
| `packages/api-client/src/use-api-fetch.test.ts` | flyorbit's, verbatim. |
| `packages/api-client/src/use-server-status.test.ts` | Generated `useGetReadiness` mocked. Healthy `data` passes through. A 503 whose body parses → `status` is the body, `error` cleared, and it wins over stale `data`. A 503 with an unparseable body, a 500, a non-`ApiError` → `error` kept. |
| `packages/components/src/layout/user-panel.test.tsx` | Skeleton, no name, when `user` is `null`. Initials: one word, two words, several words. Account item only with `onOpenProfile`, Organisation only with `onOpenOrganizationProfile`; Log out calls `onSignOut`. |
| `packages/components/src/settings/settings-dialog.test.tsx` | First tab's content shown on open; clicking another tab swaps it; `footerSlot` rendered only when passed. |
| `packages/components/src/settings/server-status-indicator.test.tsx` | Loading state. Dot colour: healthy green, degraded yellow, anything else / `error` / no `status` red. `v0.0.0` fallback. Hover-card detail present only with `showDetail`. |
| `apps/*/src/components/layout/clerk-user-panel.test.tsx` (one per portal) | `@app/auth` and `@clerk/nextjs` mocked. `"User"` / `"No email"` fallbacks; skeleton when not loaded. Organisation item only for `Role.PROJECT_MANAGER`. Log out calls `@app/auth`'s `signOut`, not Clerk's. |

The two `clerk-user-panel` tests are duplicates because the component is duplicated in each portal; each app's copy is what that app ships.

## 4. Wiring

- `Makefile`: `test-web: @cd web-app && pnpm -s test`, listed in `help`. `check` stays lint/format — tests are their own target, like `cd server && make test`.
- `.githooks/pre-push`: in the `web-app/` branch, `make -s test-web` after `make -s check-web`. Same missing-tool rule: if `web-app/node_modules/.bin/vitest` is absent, warn and let the push through.
- `apps/internal-portal/.env.example`, `apps/supplier-portal/.env.example`: drop `NODE_ENV=production`. Next sets `NODE_ENV` per command and `@next/env` never overrides one already set, so the line is inert for Next and only leaks into whatever else reads the file.

## 5. Docs

- `web-app/CLAUDE.md`: `pnpm test` / `test:watch` in Commands; a **Testing** section — runner, three projects, co-location, `.test.` vs `.spec.`, gated by pre-push, pointer to the skill; two anti-patterns (`*.spec.ts` for a Vitest file; `NODE_ENV` in an env file).
- Root `CLAUDE.md`: the pre-push paragraph mentions `make test-web`.
- `.claude/skills/web-app-testing/SKILL.md`, adapted from flyorbit: does a component earn a test (branch vs pass-through); the traps as they stand here — sidebar primitives need `{ wrapper: SidebarProvider }` and the `matchMedia` stub; test files are type-checked (`testing.d.ts`, no `.catch((e) => e)`); `NODE_ENV` pinned in the config; `isDevelopment` is a module-load constant, which `ServerStatusIndicator` already avoids by taking `showDetail` as a prop — test the prop, and hoist the same way rather than mocking the module; co-location and the `.test.`/`.spec.` split; how to add a project for a third app.

---

## Commits

1. `build(web): vitest workspace — three projects, jsdom, setup` — deps, lockfile, config, setup, and `use-api-fetch.test.ts` (the verbatim port) as the proof the workspace resolves `@app/*` and runs jsdom.
2. `fix(auth): getUserRole strips only a leading org: prefix` — `permissions.test.ts` written first and seen failing on the prefix cases, then the one-line fix. The fix needs the runner, so it follows commit 1.
3. `test(auth): the provider seam — AppUser, role, signOut`
4. `test(api-client): use-server-status recovers a degraded 503`
5. `test(components): user panel, settings dialog, server status`
6. `test(web): ClerkUserPanel in both portals`
7. `chore(web): test-web target, pre-push runs it, NODE_ENV out of .env.example`
8. `docs(web): testing section and the web-app-testing skill`

## Verification

- `make test-web` green; each test seen failing once against a deliberately broken subject before being trusted (a flipped branch, a removed `finally`).
- `pnpm type-check`, `make check-web` and `pnpm build` green — test files included (`next build` type-checks the portals' tests too).
- `NODE_ENV=production make test-web` still green (the pin holds).
- A push touching `web-app/` runs the suite in the hook; a push touching only `server/` does not.

## Out of scope

- Playwright / e2e. The `.spec.` reservation and the `e2e/**` exclude are the only nod to it.
- Coverage thresholds and CI. Pre-push is the gate.
- `query-provider.tsx`'s toast routing and the route-group cache boundary from PR #6 — the first is worth a test later; the second is React unmounting a provider.

# Web Test Suite (Vitest) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `web-app/` a Vitest + Testing Library suite covering every package and portal file with logic, gated by the pre-push hook.

**Architecture:** One `web-app/vitest.config.mts` with three inline projects (`packages`, `internal-portal`, `supplier-portal`) that inherit a jsdom root config; each portal project aliases `@/` to its own `src/`. Tests are co-located with their subjects. `make test-web` runs the suite; `.githooks/pre-push` runs it after `make check-web` when `web-app/` changed.

**Tech Stack:** Vitest 5, jsdom 30, `@vitejs/plugin-react` 6, Testing Library (react 16, dom 10, jest-dom 7, user-event 14), React 19.2.4, pnpm workspaces.

**Spec:** `docs/superpowers/specs/2026-09-25-web-vitest-design.md`

## Global Constraints

- Branch `test/web-vitest`. All commands below run from the repo root unless a `cd` is shown; the shell's cwd resets between commands, so every command carries its own `cd`.
- Dependency versions, exactly: `vitest ^5.0.1`, `jsdom ^30.0.1`, `@vitejs/plugin-react ^6.1.1`, `@testing-library/react ^16.3.3`, `@testing-library/dom ^10.4.2`, `@testing-library/jest-dom ^7.0.1`, `@testing-library/user-event ^14.6.7`, `react 19.2.4`, `react-dom 19.2.4` (exact, matching the portals).
- Test files are named `*.test.ts` / `*.test.tsx` and sit next to their subject. `*.spec.*` is reserved for Playwright and must not be used.
- `globals: false`: every test imports `describe`/`it`/`expect`/`vi` from `"vitest"`.
- Test files are type-checked by `pnpm type-check` and linted/formatted like source. Never type a caught error as `unknown` and then read from it; no `.catch((e) => e)`.
- Prettier config: no semicolons, double quotes, trailing commas. Run `pnpm exec prettier --write <files>` from `web-app/` before each commit.
- Comments are concise: state the constraint, cut the narrative (user preference).
- No server change; `make check-contract` must stay clean.

## Review Focus

1. **`signOut` ordering** — navigating before Clerk's session destroy settles would leave the session alive. Pinned in Task 3 by holding `endSession` pending and asserting `assign` has not run.
2. **`signOut` after a failed destroy** — the user must still leave the page, and the failure must still surface to the caller. Pinned in Task 3 (`rejects` + `assign` called).
3. **A `getUserRole` input without a leading `org:`** — must never grant a role. Pinned in Task 2 (`"supplier"`, `"supplierorg:"`).
4. **`NODE_ENV=production` in the caller's environment** — must not flip React to its production build under test. Pinned in Task 1 by running the suite with `NODE_ENV=production` exported.
5. **A 503 whose body is not a readiness payload** — must stay an error, not become "no status". Pinned in Task 4.

---

### Task 1: Vitest workspace

**Files:**
- Modify: `web-app/package.json`, `web-app/pnpm-lock.yaml`
- Create: `web-app/vitest.config.mts`, `web-app/vitest.setup.ts`
- Create: `web-app/packages/api-client/src/use-api-fetch.test.ts` (verbatim port)

**Interfaces:**
- Produces: `pnpm test` / `pnpm test:watch` scripts in `web-app/`; project names `packages`, `internal-portal`, `supplier-portal` (usable with `pnpm test --project <name>`); a global `window.matchMedia` stub and `NEXT_PUBLIC_API_URL` default for every test.

- [ ] **Step 1: Add the dependencies and scripts**

```bash
cd web-app && pnpm add -D -w vitest@^5.0.1 jsdom@^30.0.1 @vitejs/plugin-react@^6.1.1 @testing-library/react@^16.3.3 @testing-library/dom@^10.4.2 @testing-library/jest-dom@^7.0.1 @testing-library/user-event@^14.6.7 react@19.2.4 react-dom@19.2.4
```

Then edit `web-app/package.json` `scripts` so it reads (two new lines after `type-check`):

```json
    "type-check": "pnpm -r exec tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
```

Check `react` and `react-dom` landed as exact `19.2.4` (no `^`); fix by hand if pnpm added a caret, then `cd web-app && pnpm install`.

- [ ] **Step 2: Write `web-app/vitest.config.mts`**

```ts
import { fileURLToPath } from "node:url"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

// Vitest defaults NODE_ENV only when it is unset, so an exported
// NODE_ENV=production would load React's production build and fail every
// render test far from the cause. Pinned for every entry point.
process.env.NODE_ENV = "test"

const TEST_FILES = "src/**/*.test.?(c|m)[jt]s?(x)"

/** A portal's project: its own tests, and `@/` resolved to its own src/. */
function portal(app: string) {
  return {
    extends: true,
    resolve: {
      alias: {
        "@/": fileURLToPath(new URL(`./apps/${app}/src/`, import.meta.url)),
      },
    },
    test: { name: app, include: [`apps/${app}/${TEST_FILES}`] },
  }
}

export default defineConfig({
  plugins: [react()],
  // Every package has its own react symlink; two copies would surface as
  // "invalid hook call" from inside a primitive.
  resolve: { dedupe: ["react", "react-dom"] },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    exclude: ["**/node_modules/**", "**/.next/**", "**/dist/**", "e2e/**"],
    // Explicit imports from "vitest": globals would need a `types` entry in
    // every standalone tsconfig.
    globals: false,
    // Two portals each own `@/`, so one alias cannot serve both.
    // `.test.` only: `.spec.` is reserved for Playwright.
    projects: [
      {
        extends: true,
        test: { name: "packages", include: [`packages/*/${TEST_FILES}`] },
      },
      portal("internal-portal"),
      portal("supplier-portal"),
    ],
  },
})
```

- [ ] **Step 3: Write `web-app/vitest.setup.ts`**

```ts
import { afterEach } from "vitest"
import { cleanup } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

// Testing Library auto-cleans only with globals on.
afterEach(() => {
  cleanup()
})

// jsdom has no matchMedia, and SidebarProvider reaches it through
// useIsMobile(): every test that renders a sidebar primitive needs this.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
    addListener: () => {},
    removeListener: () => {},
  }),
})

// resolveBaseUrl() throws when unset; Next inlines it at build time, Vitest
// does not. Tests of the unset branch delete it themselves.
process.env.NEXT_PUBLIC_API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100"
```

- [ ] **Step 4: Port `use-api-fetch.test.ts` verbatim**

```bash
cp ~/projects/flyorbit/web-app/packages/api-client/src/use-api-fetch.test.ts web-app/packages/api-client/src/use-api-fetch.test.ts
diff ~/projects/flyorbit/web-app/packages/api-client/src/use-api-fetch.ts web-app/packages/api-client/src/use-api-fetch.ts
```

Expected diff: one comment line (`user's` vs `tenant's`). If the diff shows any code line, stop and adapt the test to this repo's subject before continuing.

- [ ] **Step 5: Run the suite**

Run: `cd web-app && pnpm test`
Expected: PASS — 1 file (`packages` project), all its tests green. If a test fails, read the failure against `use-api-fetch.ts`; the subject is the same as flyorbit's, so a failure means the workspace (resolution, jsdom, setup) is wrong, not the test.

- [ ] **Step 6: Prove the NODE_ENV pin (Review Focus 4)**

Run: `cd web-app && NODE_ENV=production pnpm test`
Expected: PASS, same count. (That removing the pin breaks render tests is proven in Task 5 Step 6; this file renders nothing.)

- [ ] **Step 7: Type-check, lint, format**

Run: `cd web-app && pnpm exec prettier --write package.json vitest.config.mts vitest.setup.ts packages/api-client/src/use-api-fetch.test.ts && pnpm type-check && pnpm lint && pnpm format:check`
Expected: all green. If `packages/api-client` reports missing `react-dom` types from `@testing-library/react`, add `"@types/react-dom": "^19.2.3"` to `packages/api-client/package.json` `devDependencies` and `pnpm install`.

- [ ] **Step 8: Commit**

```bash
git add web-app/package.json web-app/pnpm-lock.yaml web-app/vitest.config.mts web-app/vitest.setup.ts web-app/packages/api-client/src/use-api-fetch.test.ts web-app/packages/api-client/package.json
git commit -m "build(web): vitest workspace — three projects, jsdom, setup

One config, three inline projects: packages, and one per portal so each
resolves @/ to its own src/. NODE_ENV is pinned to test; matchMedia is
stubbed because SidebarProvider reaches it. use-api-fetch.test.ts is
flyorbit's, verbatim — the subject matches — and proves the workspace
resolves @app/* and runs jsdom."
```

---

### Task 2: `getUserRole` strips only a leading `org:`

**Files:**
- Create: `web-app/packages/auth/src/permissions.test.ts`
- Modify: `web-app/packages/auth/src/permissions.ts:19-35`

**Interfaces:**
- Consumes: `Role`, `getUserRole(orgRole: string | null | undefined): Role | null`, `isInternalRole(role: Role | null): boolean`, `isSupplierRole(role: Role | null): boolean`, `ROLE_LABELS: Record<Role, string>` — signatures unchanged.

- [ ] **Step 1: Write the failing test**

`web-app/packages/auth/src/permissions.test.ts`:

```ts
import { describe, expect, it } from "vitest"

import {
  ROLE_LABELS,
  Role,
  getUserRole,
  isInternalRole,
  isSupplierRole,
} from "./permissions"

// getUserRole is the portability seam: the only function that knows how the
// auth provider spells a role. These cases are what a migration must keep.
describe("getUserRole", () => {
  it.each([
    ["org:project_manager", Role.PROJECT_MANAGER],
    ["org:reviewer", Role.REVIEWER],
    ["org:approver", Role.APPROVER],
    ["org:supplier", Role.SUPPLIER],
  ])("narrows %s", (claim, role) => {
    expect(getUserRole(claim)).toBe(role)
  })

  it.each([
    ["an unknown role", "org:admin"],
    ["a role without the prefix", "supplier"],
    ["a prefix that is not leading", "supplierorg:"],
    ["a doubled prefix", "org:org:supplier"],
    ["the wrong case", "org:Supplier"],
    ["the bare prefix", "org:"],
  ])("returns null for %s", (_, claim) => {
    expect(getUserRole(claim)).toBeNull()
  })

  it.each([null, undefined, ""])("returns null for %j", (claim) => {
    expect(getUserRole(claim)).toBeNull()
  })
})

describe("isInternalRole / isSupplierRole", () => {
  it.each([
    [Role.PROJECT_MANAGER, true, false],
    [Role.REVIEWER, true, false],
    [Role.APPROVER, true, false],
    [Role.SUPPLIER, false, true],
    [null, false, false],
  ] as const)("%s → internal %s, supplier %s", (role, internal, supplier) => {
    expect(isInternalRole(role)).toBe(internal)
    expect(isSupplierRole(role)).toBe(supplier)
  })
})

describe("ROLE_LABELS", () => {
  it("labels every role", () => {
    for (const role of Object.values(Role)) {
      expect(ROLE_LABELS[role]).toBeTruthy()
    }
  })
})
```

- [ ] **Step 2: Run it to see it fail**

Run: `cd web-app && pnpm test packages/auth/src/permissions.test.ts`
Expected: FAIL on exactly two cases — `a role without the prefix` and `a prefix that is not leading` (both return `"supplier"`). Every other case passes.

- [ ] **Step 3: Fix `getUserRole`**

Replace the docstring and function in `web-app/packages/auth/src/permissions.ts` (the block from `/**` above `getUserRole` through its closing `}`) with:

```ts
const ORG_PREFIX = "org:"

/**
 * Convert a Clerk orgRole string to a Role value.
 *
 * Clerk prefixes every org role slug with 'org:'. Only a leading prefix is
 * stripped; a value without one, or naming no known role, is not a role.
 * Returns null when orgRole is absent (no active org context).
 *
 * @example
 * getUserRole("org:project_manager") // → "project_manager"
 * getUserRole("project_manager")     // → null
 * getUserRole(null)                  // → null
 */
export function getUserRole(orgRole: string | null | undefined): Role | null {
  if (!orgRole?.startsWith(ORG_PREFIX)) return null
  const slug = orgRole.slice(ORG_PREFIX.length)
  const values = Object.values(Role) as string[]
  return values.includes(slug) ? (slug as Role) : null
}
```

- [ ] **Step 4: Run it to see it pass**

Run: `cd web-app && pnpm test packages/auth/src/permissions.test.ts`
Expected: PASS, all cases.

- [ ] **Step 5: Type-check, lint, format, commit**

```bash
cd web-app && pnpm exec prettier --write packages/auth/src/permissions.ts packages/auth/src/permissions.test.ts && pnpm type-check && pnpm lint
cd .. && git add web-app/packages/auth/src/permissions.ts web-app/packages/auth/src/permissions.test.ts
git commit -m "fix(auth): getUserRole strips only a leading org: prefix

replace(\"org:\", \"\") stripped the first org: anywhere, so an unprefixed
\"supplier\" — or \"supplierorg:\" — came back as Role.SUPPLIER. Harmless
with what Clerk sends (every caller passes auth().orgRole, always
prefixed), but it is the portability seam and its contract should be
exact. The test pins every role, the near-misses, and the helpers."
```

---

### Task 3: The auth provider seam — role, `AppUser`, `signOut`

**Files:**
- Create: `web-app/packages/auth/src/provider.test.tsx`

**Interfaces:**
- Consumes: `AuthProvider({ children, signOutUrl = "/" })`, `useAppAuth(): { user: AppUser | null; role: Role | null; isLoaded: boolean; getToken(): Promise<string | null>; signOut(): Promise<void> }`, `AppUser = { name: string | null; email: string | null; imageUrl: string | null }` — all in `web-app/packages/auth/src/provider.tsx`.
- Clerk surface the provider reads: `useAuth()` → `{ isLoaded, orgRole, getToken, signOut }`; `useUser()` → `{ user }` with `firstName`, `lastName`, `primaryEmailAddress?.emailAddress`, `imageUrl`.

- [ ] **Step 1: Write the test**

`web-app/packages/auth/src/provider.test.tsx`:

```tsx
import type { ReactNode } from "react"
import { renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AuthProvider, useAppAuth } from "./provider"

// Only Clerk's hooks are mocked: the mapping from them to the seam's
// vendor-free context is what is under test.
const clerk = vi.hoisted(() => ({
  orgRole: "org:reviewer" as string | null,
  user: null as Record<string, unknown> | null,
  endSession: vi.fn(),
}))

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    orgRole: clerk.orgRole,
    getToken: async () => "jwt",
    signOut: clerk.endSession,
  }),
  useUser: () => ({ user: clerk.user }),
}))

const ada = {
  firstName: "Ada",
  lastName: "Lovelace",
  primaryEmailAddress: { emailAddress: "ada@test.dev" },
  imageUrl: "https://img.test/ada.png",
}

function renderAuth(signOutUrl?: string) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <AuthProvider signOutUrl={signOutUrl}>{children}</AuthProvider>
  }
  return renderHook(() => useAppAuth(), { wrapper: Wrapper }).result
}

// jsdom never navigates; swap location so assign() is observable.
const assign = vi.fn()
const realLocation = window.location

beforeEach(() => {
  clerk.orgRole = "org:reviewer"
  clerk.user = null
  clerk.endSession.mockReset()
  assign.mockReset()
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...realLocation, assign },
  })
})

afterEach(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: realLocation,
  })
})

describe("role", () => {
  it("narrows Clerk's orgRole", () => {
    expect(renderAuth().current.role).toBe("reviewer")
  })

  it("is null without an active organization", () => {
    clerk.orgRole = null
    expect(renderAuth().current.role).toBeNull()
  })
})

describe("user", () => {
  it("is AppUser: these three fields and no vendor field", () => {
    clerk.user = ada
    expect(renderAuth().current.user).toEqual({
      name: "Ada Lovelace",
      email: "ada@test.dev",
      imageUrl: "https://img.test/ada.png",
    })
  })

  it.each([
    [{ firstName: "Ada", lastName: null }, "Ada"],
    [{ firstName: null, lastName: "Lovelace" }, "Lovelace"],
    [{ firstName: null, lastName: null }, null],
    [{ firstName: "", lastName: "" }, null],
  ])("builds the name from %j as %j", (parts, name) => {
    clerk.user = { ...ada, ...parts }
    expect(renderAuth().current.user?.name).toBe(name)
  })

  it("has a null email without a primary address", () => {
    clerk.user = { ...ada, primaryEmailAddress: null }
    expect(renderAuth().current.user?.email).toBeNull()
  })

  it("has a null imageUrl when Clerk's is empty", () => {
    clerk.user = { ...ada, imageUrl: "" }
    expect(renderAuth().current.user?.imageUrl).toBeNull()
  })

  it("is null without a Clerk user", () => {
    expect(renderAuth().current.user).toBeNull()
  })
})

describe("signOut", () => {
  it("navigates only once the session has ended", async () => {
    let endSession!: () => void
    clerk.endSession.mockReturnValue(
      new Promise<void>((resolve) => {
        endSession = resolve
      }),
    )
    const auth = renderAuth("/sign-in")

    const done = auth.current.signOut()
    expect(clerk.endSession).toHaveBeenCalledWith({ redirectUrl: "/sign-in" })
    expect(assign).not.toHaveBeenCalled()

    endSession()
    await done
    expect(assign).toHaveBeenCalledWith("/sign-in")
  })

  it("navigates even when ending the session fails, and still rejects", async () => {
    clerk.endSession.mockRejectedValue(new Error("session already gone"))
    const auth = renderAuth("/sign-in")

    await expect(auth.current.signOut()).rejects.toThrow("session already gone")
    expect(assign).toHaveBeenCalledWith("/sign-in")
  })

  it("defaults to / without a signOutUrl", async () => {
    clerk.endSession.mockResolvedValue(undefined)
    const auth = renderAuth()

    await auth.current.signOut()
    expect(clerk.endSession).toHaveBeenCalledWith({ redirectUrl: "/" })
    expect(assign).toHaveBeenCalledWith("/")
  })
})
```

- [ ] **Step 2: Run it**

Run: `cd web-app && pnpm test packages/auth/src/provider.test.tsx`
Expected: PASS. The subject already exists (PR #6), so this test is written after the code; Step 3 is what proves it can fail.

- [ ] **Step 3: Prove each `signOut` test can fail**

Temporarily edit `web-app/packages/auth/src/provider.tsx`, one mutation at a time, rerun Step 2's command, confirm the named test fails, then revert with `git checkout -- web-app/packages/auth/src/provider.tsx` (the file has no uncommitted work):

1. Replace `try { await endSession(...) } finally { window.location.assign(signOutUrl) }` with `void endSession({ redirectUrl: signOutUrl }); window.location.assign(signOutUrl)` → `navigates only once the session has ended` fails.
2. Replace the whole `try { … } finally { … }` with the two lines `await endSession({ redirectUrl: signOutUrl })` and `window.location.assign(signOutUrl)` → `navigates even when ending the session fails` fails.
3. Change `imageUrl: clerkUser.imageUrl || null` to `imageUrl: clerkUser.imageUrl` → `has a null imageUrl when Clerk's is empty` fails.

After reverting: `git status --short web-app/packages/auth/src/provider.tsx` prints nothing.

- [ ] **Step 4: Type-check, lint, format, commit**

```bash
cd web-app && pnpm exec prettier --write packages/auth/src/provider.test.tsx && pnpm type-check && pnpm lint
cd .. && git add web-app/packages/auth/src/provider.test.tsx
git commit -m "test(auth): the provider seam — role, AppUser, signOut

Pins what PR #6 shipped untested: user is exactly AppUser, built from
Clerk's profile with nulls for missing parts; signOut navigates only
after the session destroy settles, navigates even when it rejects, and
defaults to /."
```

If type-check reports missing `react-dom` types for `packages/auth`, add `"@types/react-dom": "^19.2.3"` to `packages/auth/package.json` `devDependencies`, `cd web-app && pnpm install`, and include `web-app/packages/auth/package.json web-app/pnpm-lock.yaml` in the commit.

---

### Task 4: `useServerStatus` recovers a degraded 503

**Files:**
- Create: `web-app/packages/api-client/src/use-server-status.test.ts`

**Interfaces:**
- Consumes: `useServerStatus(): { status, isLoading, error }` (`web-app/packages/api-client/src/use-server-status.ts`), which calls `useGetReadiness` imported from `./generated/endpoints/system`; `ApiError(message, status, body, requestId)` from `./errors`.

- [ ] **Step 1: Write the test**

`web-app/packages/api-client/src/use-server-status.test.ts`:

```ts
import { renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "./errors"
import { useServerStatus } from "./use-server-status"

// Only the generated query hook is mocked. ApiError and the generated Zod
// validator stay real: the contract is that a 503 body survives
// GetReadinessResponse.safeParse.
const { useGetReadiness } = vi.hoisted(() => ({ useGetReadiness: vi.fn() }))

vi.mock("./generated/endpoints/system", () => ({ useGetReadiness }))

function readiness(
  overrides: { status?: "healthy" | "degraded"; version?: string } = {},
) {
  return {
    components: {
      agents_healthy: true,
      api: "healthy" as const,
      database: {
        connection_pool: {
          checked_in: 1,
          checked_out: 0,
          overflow: 0,
          size: 5,
          total: 5,
        },
        status: "healthy" as const,
      },
    },
    environment: "development" as const,
    status: overrides.status ?? ("healthy" as const),
    timestamp: "2026-09-16T12:00:00+00:00",
    version: overrides.version ?? "1.2.3",
  }
}

function mockQuery(value: { data?: unknown; isLoading?: boolean; error?: unknown }) {
  useGetReadiness.mockReturnValue({
    data: value.data,
    isLoading: value.isLoading ?? false,
    error: value.error,
  })
}

function status() {
  return renderHook(() => useServerStatus()).result.current
}

beforeEach(() => {
  useGetReadiness.mockReset()
})

describe("useServerStatus", () => {
  it("passes a successful payload straight through", () => {
    const payload = readiness()
    mockQuery({ data: payload })

    expect(status().status).toEqual(payload)
    expect(status().error).toBeUndefined()
  })

  it("recovers the degraded payload from a 503 body and clears the error", () => {
    mockQuery({
      error: new ApiError(
        "HTTP 503",
        503,
        readiness({ status: "degraded", version: "9.9.9" }),
        "req-1",
      ),
    })

    const result = status()
    expect(result.status).toMatchObject({ status: "degraded", version: "9.9.9" })
    expect(result.error).toBeUndefined()
  })

  it("prefers the recovered body over stale cached data", () => {
    mockQuery({
      data: readiness({ status: "healthy", version: "1.0.0" }),
      error: new ApiError(
        "HTTP 503",
        503,
        readiness({ status: "degraded", version: "2.0.0" }),
        "req-2",
      ),
    })

    expect(status().status).toMatchObject({ status: "degraded", version: "2.0.0" })
  })

  it("keeps the error when a 503 body is not a readiness payload", () => {
    const error = new ApiError("HTTP 503", 503, "<html>Bad Gateway</html>", "req-3")
    mockQuery({ error })

    const result = status()
    expect(result.status).toBeUndefined()
    expect(result.error).toBe(error)
  })

  it("keeps the error for any other status, next to stale data", () => {
    const stale = readiness()
    const error = new ApiError("HTTP 500", 500, { detail: "boom" }, "req-4")
    mockQuery({ data: stale, error })

    const result = status()
    expect(result.status).toEqual(stale)
    expect(result.error).toBe(error)
  })

  it("keeps an error that is not an ApiError", () => {
    const error = new TypeError("Failed to fetch")
    mockQuery({ error })

    expect(status().error).toBe(error)
  })

  it("forwards the loading flag", () => {
    mockQuery({ isLoading: true })

    expect(status().isLoading).toBe(true)
  })
})
```

- [ ] **Step 2: Run it**

Run: `cd web-app && pnpm test packages/api-client/src/use-server-status.test.ts`
Expected: PASS, 7 tests.

- [ ] **Step 3: Prove it can fail**

Temporarily change `const status = degraded ?? data` to `const status = data ?? degraded` in `use-server-status.ts`; rerun; `prefers the recovered body over stale cached data` must fail. Revert with `git checkout -- web-app/packages/api-client/src/use-server-status.ts`.

- [ ] **Step 4: Type-check, lint, format, commit**

```bash
cd web-app && pnpm exec prettier --write packages/api-client/src/use-server-status.test.ts && pnpm type-check && pnpm format:check
cd .. && git add web-app/packages/api-client/src/use-server-status.test.ts
git commit -m "test(api-client): useServerStatus recovers a degraded 503

/ready answers 503 when degraded, so the payload arrives as ApiError.body.
Pins the recovery through the real generated validator, that it beats
stale cached data, and that every other failure stays an error."
```

---

### Task 5: Components — user panel, settings dialog, server status

**Files:**
- Create: `web-app/packages/components/src/testing.d.ts`
- Create: `web-app/packages/components/src/layout/user-panel.test.tsx`
- Create: `web-app/packages/components/src/settings/settings-dialog.test.tsx`
- Create: `web-app/packages/components/src/settings/server-status-indicator.test.tsx`

**Interfaces:**
- Consumes: `UserDetailsPanel({ user: UserPanelUser | null; onSignOut; onOpenProfile?; onOpenOrganizationProfile? })` and `UserPanelUser = { name: string; email: string; imageUrl?: string }` from `./layout/user-panel`; `SettingsDialog({ tabs: SettingsTab[]; trigger?; footerSlot? })` and `SettingsTab = { id; label; icon; content }` from `./settings/settings-dialog`; `ServerStatusIndicator({ status?; isLoading; error; showDetail? })` from `./settings/server-status-indicator`; `SidebarProvider` from `@app/ui/sidebar`.
- DOM hooks the tests read: `data-slot="skeleton"`, `data-slot="sidebar-footer"`, `data-slot="hover-card-trigger"`; the status dot is `div.size-2.rounded-full` with a `bg-{green,yellow,red}-500` class.

- [ ] **Step 1: Write `testing.d.ts`**

`web-app/packages/components/src/testing.d.ts`:

```ts
// Makes jest-dom's matchers visible to tsc in this package. vitest.setup.ts
// registers them at runtime but belongs to no tsconfig, so its type
// augmentation does not reach here.
import "@testing-library/jest-dom/vitest"
```

- [ ] **Step 2: Write `user-panel.test.tsx`**

```tsx
import type { ComponentProps } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SidebarProvider } from "@app/ui/sidebar"
import { describe, expect, it, vi } from "vitest"

import { UserDetailsPanel, type UserPanelUser } from "./user-panel"

const ada: UserPanelUser = { name: "Ada Lovelace", email: "ada@test.dev" }

// useSidebar() throws outside a SidebarProvider.
function renderPanel(
  props: Partial<ComponentProps<typeof UserDetailsPanel>> = {},
) {
  const onSignOut = vi.fn()
  render(<UserDetailsPanel user={ada} onSignOut={onSignOut} {...props} />, {
    wrapper: SidebarProvider,
  })
  return { onSignOut }
}

async function openMenu() {
  await userEvent.click(screen.getByRole("button", { name: /Ada Lovelace/ }))
}

describe("UserDetailsPanel", () => {
  it("renders a skeleton and no user while there is none", () => {
    renderPanel({ user: null })

    expect(document.querySelector('[data-slot="skeleton"]')).not.toBeNull()
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument()
  })

  it.each([
    ["Ada", "A"],
    ["Ada Lovelace", "AL"],
    ["Ada King Lovelace", "AL"],
    ["  ada lovelace  ", "AL"],
  ])("shows %j as the initials %s", (name, initials) => {
    renderPanel({ user: { ...ada, name } })

    expect(screen.getByText(initials)).toBeInTheDocument()
  })

  it("offers only Log out without profile handlers", async () => {
    const { onSignOut } = renderPanel()
    await openMenu()

    const logOut = await screen.findByRole("menuitem", { name: /Log out/ })
    expect(screen.queryByRole("menuitem", { name: /Account/ })).not.toBeInTheDocument()
    expect(
      screen.queryByRole("menuitem", { name: /Organisation/ }),
    ).not.toBeInTheDocument()

    await userEvent.click(logOut)
    expect(onSignOut).toHaveBeenCalledOnce()
  })

  it("offers Account alone when given only onOpenProfile", async () => {
    const onOpenProfile = vi.fn()
    renderPanel({ onOpenProfile })
    await openMenu()

    const account = await screen.findByRole("menuitem", { name: /Account/ })
    expect(
      screen.queryByRole("menuitem", { name: /Organisation/ }),
    ).not.toBeInTheDocument()

    await userEvent.click(account)
    expect(onOpenProfile).toHaveBeenCalledOnce()
  })

  it("offers Organisation alone when given only onOpenOrganizationProfile", async () => {
    const onOpenOrganizationProfile = vi.fn()
    renderPanel({ onOpenOrganizationProfile })
    await openMenu()

    const organisation = await screen.findByRole("menuitem", {
      name: /Organisation/,
    })
    expect(screen.queryByRole("menuitem", { name: /Account/ })).not.toBeInTheDocument()

    await userEvent.click(organisation)
    expect(onOpenOrganizationProfile).toHaveBeenCalledOnce()
  })
})
```

The absence checks run after `findByRole` has proven the menu is open and before the click, which may close it — so they cannot pass vacuously.

- [ ] **Step 3: Write `settings-dialog.test.tsx`**

```tsx
import type { ReactElement } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SidebarProvider } from "@app/ui/sidebar"
import { describe, expect, it } from "vitest"

import { SettingsDialog, type SettingsTab } from "./settings-dialog"

const TABS: SettingsTab[] = [
  {
    id: "general",
    label: "General",
    icon: <svg />,
    content: <p>General body</p>,
  },
  {
    id: "account",
    label: "Account",
    icon: <svg />,
    content: <p>Account body</p>,
  },
]

// The tab rail is built from sidebar primitives, which throw outside a
// SidebarProvider. The dialog is closed until its trigger is clicked.
async function open(ui: ReactElement) {
  const user = userEvent.setup()
  render(ui, { wrapper: SidebarProvider })
  await user.click(screen.getByRole("button", { name: /settings/i }))
  return user
}

describe("SettingsDialog", () => {
  it("shows the first tab on open", async () => {
    await open(<SettingsDialog tabs={TABS} />)

    expect(await screen.findByText("General body")).toBeInTheDocument()
    expect(screen.queryByText("Account body")).not.toBeInTheDocument()
  })

  it("switches content when another tab is clicked", async () => {
    const user = await open(<SettingsDialog tabs={TABS} />)

    await user.click(await screen.findByRole("button", { name: "Account" }))

    expect(await screen.findByText("Account body")).toBeInTheDocument()
    expect(screen.queryByText("General body")).not.toBeInTheDocument()
  })

  it("renders the footer slot when given one", async () => {
    await open(<SettingsDialog tabs={TABS} footerSlot={<p>Footer here</p>} />)

    expect(await screen.findByText("Footer here")).toBeInTheDocument()
  })

  it("renders no footer without one", async () => {
    await open(<SettingsDialog tabs={TABS} />)
    await screen.findByText("General body")

    expect(document.querySelector('[data-slot="sidebar-footer"]')).toBeNull()
  })
})
```

- [ ] **Step 4: Write `server-status-indicator.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ServerStatusIndicator } from "./server-status-indicator"

function readiness(status: string) {
  return {
    status,
    version: "1.2.3",
    environment: "development",
    timestamp: "2026-09-16T12:00:00+00:00",
    components: {
      api: "healthy",
      database: { status: "healthy" },
      agents: { chatbot: { ready: true } },
    },
  }
}

/** The status dot carries its state in a Tailwind colour class. */
function dotClasses() {
  return document.querySelector("div.size-2.rounded-full")?.className ?? ""
}

describe("ServerStatusIndicator", () => {
  it("shows a loading placeholder", () => {
    render(<ServerStatusIndicator isLoading error={undefined} />)

    expect(screen.getByText("Loading...")).toBeInTheDocument()
  })

  it("is green and pinging when healthy", () => {
    render(
      <ServerStatusIndicator
        status={readiness("healthy")}
        isLoading={false}
        error={undefined}
      />,
    )

    expect(dotClasses()).toContain("bg-green-500")
    expect(document.querySelector(".animate-ping")).not.toBeNull()
    expect(screen.getByText("v1.2.3")).toBeInTheDocument()
  })

  it("is yellow and still when degraded", () => {
    render(
      <ServerStatusIndicator
        status={readiness("degraded")}
        isLoading={false}
        error={undefined}
      />,
    )

    expect(dotClasses()).toContain("bg-yellow-500")
    expect(document.querySelector(".animate-ping")).toBeNull()
  })

  it("is red for any other status", () => {
    render(
      <ServerStatusIndicator
        status={readiness("unhealthy")}
        isLoading={false}
        error={undefined}
      />,
    )

    expect(dotClasses()).toContain("bg-red-500")
  })

  it("is red with v0.0.0 when there is no status", () => {
    render(<ServerStatusIndicator isLoading={false} error={undefined} />)

    expect(dotClasses()).toContain("bg-red-500")
    expect(screen.getByText("v0.0.0")).toBeInTheDocument()
  })

  it("is red when an error is present even beside a healthy payload", () => {
    // `error || !status` is tested first; useServerStatus clears the error
    // when it recovers a degraded body, or the dot would stay red.
    render(
      <ServerStatusIndicator
        status={readiness("healthy")}
        isLoading={false}
        error={new Error("boom")}
      />,
    )

    expect(dotClasses()).toContain("bg-red-500")
  })

  it("has no hover card without showDetail", () => {
    render(
      <ServerStatusIndicator
        status={readiness("healthy")}
        isLoading={false}
        error={undefined}
      />,
    )

    expect(document.querySelector('[data-slot="hover-card-trigger"]')).toBeNull()
  })

  it("wraps the indicator in a hover card with showDetail", () => {
    render(
      <ServerStatusIndicator
        status={readiness("healthy")}
        isLoading={false}
        error={undefined}
        showDetail
      />,
    )

    expect(
      document.querySelector('[data-slot="hover-card-trigger"]'),
    ).not.toBeNull()
  })
})
```

- [ ] **Step 5: Run the package's tests**

Run: `cd web-app && pnpm test packages/components`
Expected: PASS, 3 files. Common failures and their cause:
- `useSidebar must be used within a SidebarProvider` → a render is missing `{ wrapper: SidebarProvider }`.
- `window.matchMedia is not a function` → `vitest.setup.ts` did not load; check `setupFiles` in the config.
- A menu item never appears → Base UI renders the popup asynchronously; use `findByRole`, not `getByRole`.

- [ ] **Step 6: Prove the render tests need the NODE_ENV pin (Review Focus 4)**

Temporarily delete `process.env.NODE_ENV = "test"` from `vitest.config.mts`; run `cd web-app && NODE_ENV=production pnpm test packages/components`; expect failures. Restore the line; rerun; expect PASS.

- [ ] **Step 7: Prove the branch tests can fail**

One at a time, rerun Step 5 and revert with `git checkout -- <file>`:
1. In `user-panel.tsx`, change `{onOpenOrganizationProfile && (` to `{true && (` → `offers Account alone…` or `offers only Log out…` fails. (Type-check is not run here; the mutation is transient.)
2. In `settings-dialog.tsx`, change `{footerSlot && <SidebarFooter>{footerSlot}</SidebarFooter>}` to `<SidebarFooter>{footerSlot}</SidebarFooter>` → `renders no footer without one` fails.
3. In `server-status-indicator.tsx`, change `: status.status === "degraded"` to `: status.status === "unhealthy"` → `is yellow and still when degraded` fails.

- [ ] **Step 8: Type-check, lint, format, commit**

```bash
cd web-app && pnpm exec prettier --write packages/components/src && pnpm type-check && pnpm lint && pnpm format:check
cd .. && git add web-app/packages/components/src
git commit -m "test(components): user panel, settings dialog, server status

The three chrome components with branches: the panel's skeleton,
initials and optional menu items; the dialog's tab state and footer
slot; the indicator's status colours and showDetail hover card. The
first two render sidebar primitives, so they render inside a
SidebarProvider — which is what the matchMedia stub is for."
```

---

### Task 6: `ClerkUserPanel` in both portals

**Files:**
- Create: `web-app/apps/internal-portal/src/testing.d.ts`, `web-app/apps/supplier-portal/src/testing.d.ts`
- Create: `web-app/apps/internal-portal/src/components/layout/clerk-user-panel.test.tsx`
- Create: `web-app/apps/supplier-portal/src/components/layout/clerk-user-panel.test.tsx`

**Interfaces:**
- Consumes: `ClerkUserPanel()` in each portal's `src/components/layout/clerk-user-panel.tsx` (identical in both), which reads `useAppAuth()` → `{ isLoaded, user: AppUser | null, role, signOut }` and `Role` from `@app/auth`, and `useClerk()` → `{ openUserProfile, openOrganizationProfile }` from `@clerk/nextjs`, and renders `UserDetailsPanel` (Task 5).

- [ ] **Step 1: Confirm the two subjects are identical**

Run: `diff web-app/apps/internal-portal/src/components/layout/clerk-user-panel.tsx web-app/apps/supplier-portal/src/components/layout/clerk-user-panel.tsx`
Expected: no output. If they differ, write the supplier test against its own subject instead of copying in Step 4.

- [ ] **Step 2: Write both `testing.d.ts` files**

Same content in `web-app/apps/internal-portal/src/testing.d.ts` and `web-app/apps/supplier-portal/src/testing.d.ts`:

```ts
// Makes jest-dom's matchers visible to tsc in this app. vitest.setup.ts
// registers them at runtime but belongs to no tsconfig, so its type
// augmentation does not reach here.
import "@testing-library/jest-dom/vitest"
```

- [ ] **Step 3: Write the internal portal's test**

`web-app/apps/internal-portal/src/components/layout/clerk-user-panel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { Role } from "@app/auth"
import { SidebarProvider } from "@app/ui/sidebar"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ClerkUserPanel } from "./clerk-user-panel"

const mocks = vi.hoisted(() => ({
  auth: {} as Record<string, unknown>,
  signOut: vi.fn(),
  clerk: {
    openUserProfile: vi.fn(),
    openOrganizationProfile: vi.fn(),
    signOut: vi.fn(),
  },
}))

// Role stays real; only the hook is replaced.
vi.mock("@app/auth", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@app/auth")>()),
  useAppAuth: () => mocks.auth,
}))

vi.mock("@clerk/nextjs", () => ({ useClerk: () => mocks.clerk }))

function setAuth(overrides: Record<string, unknown> = {}) {
  mocks.auth = {
    isLoaded: true,
    role: Role.REVIEWER,
    user: { name: "Ada Lovelace", email: "ada@test.dev", imageUrl: null },
    signOut: mocks.signOut,
    ...overrides,
  }
}

function renderPanel() {
  render(<ClerkUserPanel />, { wrapper: SidebarProvider })
}

async function openMenu(name: RegExp) {
  await userEvent.click(screen.getByRole("button", { name }))
}

beforeEach(() => {
  vi.clearAllMocks()
  setAuth()
})

describe("ClerkUserPanel", () => {
  it("renders the skeleton until auth has loaded", () => {
    setAuth({ isLoaded: false })
    renderPanel()

    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument()
  })

  it("falls back to User and No email", () => {
    setAuth({ user: { name: null, email: null, imageUrl: null } })
    renderPanel()

    expect(screen.getByText("User")).toBeInTheDocument()
    expect(screen.getByText("No email")).toBeInTheDocument()
  })

  it("opens Clerk's profile from Account", async () => {
    renderPanel()
    await openMenu(/Ada Lovelace/)

    await userEvent.click(await screen.findByRole("menuitem", { name: /Account/ }))
    expect(mocks.clerk.openUserProfile).toHaveBeenCalledOnce()
  })

  it("offers Organisation to a project manager", async () => {
    setAuth({ role: Role.PROJECT_MANAGER })
    renderPanel()
    await openMenu(/Ada Lovelace/)

    await userEvent.click(
      await screen.findByRole("menuitem", { name: /Organisation/ }),
    )
    expect(mocks.clerk.openOrganizationProfile).toHaveBeenCalledOnce()
  })

  it.each([Role.REVIEWER, Role.APPROVER, Role.SUPPLIER, null])(
    "does not offer Organisation to %s",
    async (role) => {
      setAuth({ role })
      renderPanel()
      await openMenu(/Ada Lovelace/)

      await screen.findByRole("menuitem", { name: /Log out/ })
      expect(
        screen.queryByRole("menuitem", { name: /Organisation/ }),
      ).not.toBeInTheDocument()
    },
  )

  it("signs out through @app/auth, never Clerk directly", async () => {
    renderPanel()
    await openMenu(/Ada Lovelace/)

    await userEvent.click(await screen.findByRole("menuitem", { name: /Log out/ }))
    expect(mocks.signOut).toHaveBeenCalledOnce()
    expect(mocks.clerk.signOut).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 4: Copy it to the supplier portal**

```bash
cp web-app/apps/internal-portal/src/components/layout/clerk-user-panel.test.tsx web-app/apps/supplier-portal/src/components/layout/clerk-user-panel.test.tsx
```

- [ ] **Step 5: Run both portal projects**

Run: `cd web-app && pnpm test --project internal-portal --project supplier-portal`
Expected: PASS, 2 files. If `@app/auth`'s real module fails to import because `@clerk/nextjs` lacks `useAuth`/`useUser`, add them to the `@clerk/nextjs` mock as `useAuth: vi.fn(), useUser: vi.fn()` in both files.

- [ ] **Step 6: Prove it can fail**

In the internal portal's `clerk-user-panel.tsx`, change `role === Role.PROJECT_MANAGER` to `role !== null`; rerun Step 5; the `does not offer Organisation to reviewer` / `approver` / `supplier` cases fail in `internal-portal` only. Revert with `git checkout -- web-app/apps/internal-portal/src/components/layout/clerk-user-panel.tsx`.

- [ ] **Step 7: Full suite, type-check, lint, build, commit**

```bash
cd web-app && pnpm exec prettier --write apps/internal-portal/src apps/supplier-portal/src && pnpm test && pnpm type-check && pnpm lint && pnpm format:check && pnpm build
cd .. && git add web-app/apps/internal-portal/src web-app/apps/supplier-portal/src
git commit -m "test(web): ClerkUserPanel in both portals

The panel is duplicated per portal, so each copy has its own test:
fallbacks, the PM-only Organisation item, and Log out going through
@app/auth's signOut rather than Clerk's."
```

`pnpm build` matters here: `next build` type-checks everything the portal's tsconfig includes, so the new test files are compiled by the image build too.

---

### Task 7: Wiring — `make test-web`, the pre-push gate, `.env.example`

**Files:**
- Modify: `Makefile` (`.PHONY` line 1; help block around line 52; after `check-web` around line 175)
- Modify: `.githooks/pre-push` (header comment lines 2-10; the `web-app/` block)
- Modify: `web-app/apps/internal-portal/.env.example:1-2`, `web-app/apps/supplier-portal/.env.example:1-2`

**Interfaces:**
- Produces: `make test-web` (runs `pnpm -s test` in `web-app/`).

- [ ] **Step 1: Makefile**

Add `test-web` to `.PHONY` after `check-web`. In the help block, change the `make check` line and add one after `make check-web`:

```make
	@echo "  make check              - Lint and format-check both sides (pre-push runs these, plus test-web)"
	@echo "  make check-server       - ruff check + ruff format --check + lint-imports"
	@echo "  make check-web          - pnpm lint + pnpm format:check"
	@echo "  make test-web           - Vitest unit and component tests (web-app)"
```

After the `check-web` target:

```make

# Tests, not a check: `check` stays read-only lint/format. No NODE_ENV here —
# vitest.config.mts pins it, whatever the -include'd .env.local exports.
test-web:
	@cd web-app && pnpm -s test
```

- [ ] **Step 2: pre-push**

Replace the header's first paragraph (lines 2-6) with:

```bash
# Lint, format-check and test before anything leaves the machine.
#
# Runs `make check-server` when server/ changed, and `make check-web` then
# `make test-web` when web-app/ changed, measured against the upstream branch
# (or every commit, for a branch pushed the first time). Same install as the
# pre-commit hook:
```

(keep the `git config core.hooksPath .githooks` line and the rest). Replace the `web-app/` block with:

```bash
if grep -qE '^web-app/' <<<"$CHANGED"; then
  if command -v pnpm >/dev/null 2>&1 && [ -x web-app/node_modules/.bin/prettier ]; then
    echo "pre-push: checking web-app/ ..." >&2
    make -s check-web
    if [ -x web-app/node_modules/.bin/vitest ]; then
      echo "pre-push: testing web-app/ ..." >&2
      make -s test-web
    else
      missing "web-app/node_modules/.bin/vitest" "web-app test"
    fi
  else
    missing "pnpm or web-app/node_modules" web-app
  fi
fi
```

- [ ] **Step 3: Drop `NODE_ENV` from both `.env.example` files**

Delete the `# Node environment` comment and the `NODE_ENV=production` line (and the blank line after them) from `web-app/apps/internal-portal/.env.example` and `web-app/apps/supplier-portal/.env.example`. Then confirm nothing else reads it from there: `git grep -n NODE_ENV -- web-app/apps` should show no `.env.example` hit.

- [ ] **Step 4: Verify**

```bash
make test-web
make help | grep -n test-web
bash -n .githooks/pre-push
NODE_ENV=production make test-web
```

Expected: suite green twice; the help line printed; `bash -n` silent. Then run the hook's logic against a real diff without pushing: `.githooks/pre-push` (it only reads `git diff`, pushes nothing); expected output includes `pre-push: checking web-app/ ...` and `pre-push: testing web-app/ ...` and exits 0.

- [ ] **Step 5: Commit**

```bash
git add Makefile .githooks/pre-push web-app/apps/internal-portal/.env.example web-app/apps/supplier-portal/.env.example
git commit -m "chore(web): test-web target, pre-push runs it, NODE_ENV out of .env.example

The pre-push hook is the only gate for web checks — no CI runs them —
and the suite is seconds of jsdom, so it runs after check-web whenever
web-app/ changed. Missing vitest warns and lets the push through, like
the other tools.

NODE_ENV=production in .env.example was inert for Next (it sets
NODE_ENV per command) and leaked into everything else the root
Makefile's -include exports: a fork copying the example ran its tests
under React's production build. The config pins it anyway."
```

---

### Task 8: Docs — `web-app/CLAUDE.md`, root `CLAUDE.md`, the `web-app-testing` skill

**Files:**
- Modify: `web-app/CLAUDE.md` (Dev Commands block ~line 105; new `## Testing` section before `## Skills to Use`; Skills table; Common Pitfalls)
- Modify: `CLAUDE.md` (the pre-push paragraph, ~line 231)
- Create: `.claude/skills/web-app-testing/SKILL.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: `web-app/CLAUDE.md`**

In the Dev Commands code block, after the `type-check` line add:

```bash
pnpm test                  # Vitest, once (also `make test-web` from the repo root)
pnpm test:watch            # Vitest in watch mode
```

Insert before `## Skills to Use`:

```markdown
## Testing

Vitest + Testing Library in jsdom. One config, `vitest.config.mts`, with three
projects: `packages` (every `packages/*/src`), `internal-portal` and
`supplier-portal` — one per portal because each resolves `@/` to its own `src/`.
A third app needs a third `portal(...)` line there.

`pnpm test`, or `make test-web` from the repo root. **The pre-push hook runs it**
after `make check-web` whenever `web-app/` changed; there is no CI.

**Tests are co-located with their subjects** — `user-panel.test.tsx` next to
`user-panel.tsx` — so a test moves with `git mv` when a component is promoted
between packages. This diverges from `server/tests/` on purpose.

**`*.test.*` is Vitest. `*.spec.*` is reserved for Playwright** and excluded from
the run.

Before writing or debugging a test, read the **`/web-app-testing`** skill: the
sidebar/`matchMedia` trap, type-checked test files, the pinned `NODE_ENV` and
module-load constants all fail far from their cause.
```

Add a row to the Skills table:

```markdown
| Writing, running or debugging any test | `/web-app-testing` |
```

Add to Common Pitfalls:

```markdown
- Naming a Vitest file `*.spec.ts` — that suffix is reserved for Playwright and excluded from the run
- Putting `NODE_ENV` in an env file — Next sets it per command; anywhere else it leaks into (the root Makefile exports `internal-portal/.env.local`) it decides how React builds under test
```

- [ ] **Step 2: Root `CLAUDE.md`**

Replace the paragraph starting `Two hooks live there.` with:

```markdown
Two hooks live there. `pre-commit` keeps the API contract in sync (see **API
Contract** below). `pre-push` runs `make check-server` and `make check-web`
for whichever side changed since the upstream branch: ruff and Prettier in
check mode, plus ESLint — and, for `web-app/`, `make test-web` (Vitest).
There is no CI for these, so the hook is the gate; `make check` runs both
checks by hand and `git push --no-verify` skips it once.
`.vscode/settings.json` formats on save with the same tools, so the hook
rarely has anything to say.
```

- [ ] **Step 3: `.claude/skills/web-app-testing/SKILL.md`**

```markdown
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

### 4. Module-load constants cover half a component

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
```

- [ ] **Step 4: Check and commit**

```bash
cd web-app && pnpm format:check
cd .. && git add web-app/CLAUDE.md CLAUDE.md .claude/skills/web-app-testing/SKILL.md
git commit -m "docs(web): testing section and the web-app-testing skill"
```

---

## Final verification (after Task 8)

```bash
make test-web
NODE_ENV=production make test-web
cd web-app && pnpm type-check && pnpm lint && pnpm format:check && pnpm build
cd .. && make check-contract
git status --short        # clean
git log --oneline main..  # spec commit + 8 task commits
```

# Clerk & RBAC Architecture Design

**Date:** 2026-04-11  
**Status:** Approved  
**Scope:** Clerk Dashboard setup, role abstraction layer, supplier invitation architecture principle

---

## Context

Rilevio is a B2B SaaS multi-tenant platform. Each customer (tenant) maps to one Clerk Organization. There are two separate portals: the internal portal (project managers, reviewers, approvers) and the supplier portal (external suppliers). Only admins can add users — no self-registration.

Post-prototype requirements include ISO 27001 + SOC2 compliance and a potential migration from Clerk to WorkOS. The design prioritises portability without adding premature infrastructure.

---

## Section 1 — Clerk Dashboard Setup

### Steps

1. **Enable Organizations**  
   Dashboard → Organizations → Enable

2. **Disable personal accounts**  
   Users & Authentication → Personal accounts → Off  
   Every user must always operate within an org context.

3. **Disable self-registration**  
   Users & Authentication → Email, phone, username → Restrict sign-ups to invitations only  
   New users only enter the platform via invitation email.

4. **Create custom org roles** (Dashboard → Organizations → Roles):
   | Clerk slug | Display (IT) | Portal |
   |---|---|---|
   | `org:project_manager` | Project Manager | Internal |
   | `org:reviewer` | Revisore | Internal |
   | `org:approver` | Approvatore | Internal |
   | `org:supplier` | Fornitore | Supplier |

   Set `org:supplier` as the default invitation role (most restrictive). Keep `org:admin` for the tenant admin who manages org membership — this role has no app-level access, only org management rights in Clerk.

5. **Tenant onboarding (prototype)**  
   Manual: dev/admin creates the Clerk Organization from the dashboard and invites the first PM with `org:admin` rights. No self-service onboarding UI for the prototype.

### JWT Claims

When a user is in an org context, the Clerk JWT includes:

```
sub        → Clerk user ID (already extracted)
org_id     → Clerk organization ID  ← new
org_role   → e.g. "org:project_manager"  ← new
org_slug   → org URL slug
```

---

## Section 2 — Role Abstraction Layer

The abstraction layer is the portability seam. All role-related logic passes through a single module on each side. When migrating to WorkOS (or a DB-backed role table), only these modules change — no endpoint or component changes.

### 2a — Backend (FastAPI)

#### AuthMiddleware — extract org claims

Extend the existing `AuthMiddleware` to store org claims from the decoded JWT payload into `request.state`. The JWT is already decoded; this is two extra lines:

```python
request.state.org_id   = payload.get("org_id")
request.state.org_role = payload.get("org_role", "").removeprefix("org:")
# "org:project_manager" → "project_manager"
```

#### Role enum — `app/models/enums.py` (or similar)

```python
from enum import StrEnum

class Role(StrEnum):
    PROJECT_MANAGER = "project_manager"
    REVIEWER        = "reviewer"
    APPROVER        = "approver"
    SUPPLIER        = "supplier"
```

#### Dependencies — `app/api/dependencies/auth.py`

Add the following alongside the existing `get_current_user` / `CurrentUser`:

```python
# The seam — only this function changes when migrating to WorkOS/DB:
def get_current_role(request: Request) -> Role:
    raw = getattr(request.state, "org_role", None)
    if not raw:
        raise AuthorizationError("No organization role in token")
    try:
        return Role(raw)
    except ValueError:
        raise AuthorizationError(f"Unknown role: {raw}")


def require_role(*allowed: Role):
    """Dependency factory for role-gated endpoints."""
    def dependency(role: Role = Depends(get_current_role)) -> None:
        if role not in allowed:
            raise AuthorizationError("Insufficient permissions")
    return Depends(dependency)


# Convenience aliases used in endpoint signatures:
InternalUserRole = require_role(Role.PROJECT_MANAGER, Role.REVIEWER, Role.APPROVER)
PMOnly           = require_role(Role.PROJECT_MANAGER)
SupplierRole     = require_role(Role.SUPPLIER)
```

Usage in endpoints:

```python
@router.get("/projects", dependencies=[InternalUserRole])
async def list_projects(user: CurrentUser, session: DbSession): ...

@router.post("/invitations", dependencies=[PMOnly])
async def invite_supplier(user: CurrentUser, ...): ...
```

#### User model — add `org_id`

Add `org_id` to the `User` model for tenant-scoped DB queries. `org_role` is intentionally excluded — it is auth context, not identity data, and keeping it only in `request.state` avoids sync issues.

```python
org_id: Optional[str] = Field(default=None, index=True)
```

#### JIT provisioning — update `get_or_create_user`

`get_current_user` already has access to `request`. Pass `org_id` from `request.state` to the user provisioning call so it is stored on first login and kept up to date:

```python
async def get_current_user(request: Request, session: DbSession, ...) -> User:
    org_id = getattr(request.state, "org_id", None)
    user = await user_provider.get_or_create_user(clerk_id, org_id, session)
    ...
```

`get_or_create_user` upserts `org_id` on the User record each time (handles the case where an admin re-assigns a user to a different org in the future).

---

### 2b — Frontend (`packages/auth`)

A dedicated `packages/auth` package contains all shared auth logic. It is intentionally separate from `packages/ui` (visual components) because auth logic has a different change cadence, different owners, and is the primary migration seam when switching to WorkOS.

```
web-app/packages/auth/
├── package.json          # name: "@repo/auth"
└── src/
    ├── permissions.ts    # Role enum, getUserRole(), isInternalRole(), ROLE_LABELS
    ├── provider.tsx      # AuthProvider + useAppAuth() hook
    └── index.ts          # barrel export
```

#### Role types — `packages/auth/src/permissions.ts`

```typescript
export const Role = {
  PROJECT_MANAGER: "project_manager",
  REVIEWER:        "reviewer",
  APPROVER:        "approver",
  SUPPLIER:        "supplier",
} as const
export type Role = (typeof Role)[keyof typeof Role]

// The seam — only this function changes when migrating to WorkOS:
export function getUserRole(orgRole: string | null | undefined): Role | null {
  if (!orgRole) return null
  return (orgRole.replace("org:", "") as Role) ?? null
}

// Internal = any non-supplier role
export function isInternalRole(role: Role | null): boolean {
  return role !== null && role !== Role.SUPPLIER
}

// Italian display labels — mapped in frontend only
export const ROLE_LABELS: Record<Role, string> = {
  project_manager: "Project Manager",
  reviewer:        "Revisore",
  approver:        "Approvatore",
  supplier:        "Fornitore",
}
```

#### Auth Provider — `packages/auth/src/provider.tsx`

A React Context Provider centralises identity, role, and loading state. Components call `useAppAuth()` — they never call Clerk's `useAuth()` or `useUser()` directly. This makes `AuthProvider` the second portability seam: when migrating to WorkOS, only its internals change.

**Why Context, not Zustand:** Zustand is for client-managed state that changes through user actions. Auth state is external state owned by Clerk's SDK — Clerk already manages it globally via `ClerkProvider`. Adding Zustand creates two sources of truth and a sync risk (e.g., org switch updates Clerk but not the store). Context is the right primitive for "here is the current identity, available anywhere in the tree."

```tsx
'use client'
import { createContext, useContext } from 'react'
import { useAuth, useUser } from '@clerk/nextjs'
import { getUserRole, Role } from './permissions'
import type { UserResource } from '@clerk/types'

interface AuthContextValue {
  user: UserResource | null | undefined
  role: Role | null
  isLoaded: boolean
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  role: null,
  isLoaded: false,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isLoaded, orgRole } = useAuth()
  const { user } = useUser()
  const role = getUserRole(orgRole)

  return (
    <AuthContext.Provider value={{ user, role, isLoaded }}>
      {children}
    </AuthContext.Provider>
  )
}

// The only hook components should call for auth state:
export function useAppAuth() {
  return useContext(AuthContext)
}
```

`AuthProvider` is added inside `ClerkProvider` in each app's root layout. Both portals share the same provider from `@repo/auth`.

**What stays out of the provider:** data fetching, user preferences, org metadata — all TanStack Query territory.

**Rule:** No component ever calls `useAuth()`, `useUser()`, or `has()` directly. All auth state comes from `useAppAuth()`. Role checks use `role === Role.PROJECT_MANAGER` against the value returned by `useAppAuth()`.

#### Middleware — portal-level enforcement (`proxy.ts`)

In Next.js 16 the middleware file is named `proxy.ts` (not `middleware.ts`). Both portals already have a `proxy.ts`. The current implementation reads `sessionClaims.metadata.role` — **this is a bug**: it reads user-level public metadata, not the org membership role. It must be updated to read `orgRole` from `auth()` and pass it through `getUserRole()`.

`proxy.ts` imports from `@repo/auth` for the role utilities but owns its own portal-specific redirect logic — the two portals have opposite rules and must not share this file.

```typescript
// internal-portal: proxy.ts
import { getUserRole, isInternalRole } from '@repo/auth'

const { orgRole } = await auth()
const role = getUserRole(orgRole)

if (!role || !isInternalRole(role)) {
  return NextResponse.redirect(new URL('/unauthorized', req.url))
}

// supplier-portal: proxy.ts
import { getUserRole, Role } from '@repo/auth'

const { orgRole } = await auth()
const role = getUserRole(orgRole)
if (role !== Role.SUPPLIER) {
  return NextResponse.redirect(new URL('/unauthorized', req.url))
}
```

#### Conditional rendering

This project uses `@clerk/nextjs` v6 (Core 2). Use `<Protect>` for declarative role-gated rendering — **not** `<Show>`, which is only available in the current SDK (v7+).

```tsx
import { Protect } from '@clerk/nextjs'

<Protect role="org:project_manager">
  <InviteButton />
</Protect>
```

For programmatic checks, use `useAppAuth()` — never `useAuth()` or `has()` directly:

```typescript
'use client'
import { useAppAuth } from '@repo/auth'
import { Role } from '@repo/auth'

const { role, isLoaded } = useAppAuth()

if (!isLoaded) return <Skeleton />
if (role === Role.PROJECT_MANAGER) {
  // show invite button
}
```

> **Migration note (v7+):** Replace `<Protect>` with `<Show when={{ role: "org:project_manager" }}>`. Replace `AuthProvider` internals with WorkOS equivalents. No component call sites change.

---

## Section 3 — Supplier Invitation: Architecture Principle

*(Endpoints are out of scope for the prototype. This section records the architecture decision only.)*

All Clerk API calls that mutate org state (invitations, member removal, role changes) originate from the FastAPI backend — never from the frontend directly. The Clerk secret key stays server-side.

The existing `ClerkService` (`app/services/clerk/service.py`) already wraps the `clerk_backend_api` SDK. When invitation endpoints are built, org-related methods (`invite_member`, `revoke_invitation`, `list_members`) are added to `ClerkService` — not to a separate utility. `ClerkService` is the single Clerk API boundary in the backend; when migrating to WorkOS, it is the only file that changes.

```
PM (internal portal)
  → POST /api/v1/invitations  { email, role }   ← future endpoint
    → FastAPI: role check (PMOnly)
    → ClerkService.invite_member(org_id, email, role, redirect_url)
    → Clerk sends invitation email
Supplier accepts → creates Clerk account → lands on supplier portal
```

---

## Migration Path to WorkOS / DB Roles

When post-prototype compliance work begins:

| What changes | What stays the same |
|---|---|
| `AuthMiddleware` reads `org_role` from DB instead of JWT | All endpoints, all role checks |
| `ClerkService` replaced by `WorkOSService` | `Role` enum, `require_role()` factory |
| `AuthProvider` internals rewritten for WorkOS | `useAppAuth()` — all component call sites |
| `getUserRole()` internals updated | All `proxy.ts` routing logic |
| Add audit log table for access grants | `InternalUserRole`, `PMOnly`, `SupplierRole` aliases |

The seams are explicit and contained to three locations: `get_current_role` (backend), `getUserRole` (frontend utility), and `AuthProvider` (frontend state). No endpoint, component, or route handler knows which auth provider is in use.

---

## Out of Scope (prototype)

- Multi-org users (one user, multiple tenants)
- Self-service tenant onboarding UI
- Audit log table for access grants
- Periodic access review workflow
- Enterprise SSO (SAML/OIDC) per org

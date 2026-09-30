# Authorization — tenants, roles, and where each check runs

Who may see and change what: the tenant boundary, the four roles, and the layer that
enforces each rule on the server and in the portals. How a token is verified and a user
provisioned is authentication, and is in [`authentication.md`](./authentication.md).
Setting up the roles in Clerk is [`setup/clerk.md`](../setup/clerk.md). This describes the
system as it stands and is kept current.

---

## 1. The model

**A tenant is a Clerk Organization.** Every user who can do anything belongs to one, with
one selected as active; the session token carries its id and the user's role in it. There
is no tenant table and no tenant id of our own.

**A role is a Clerk organization role**, one per membership, and arrives on the token —
not user metadata, and not a column of ours. The four are the example domain's; what each
is for, and which portal it lands in, is
[`features/account.md`](../product/features/account.md) §3.

The slugs are English because they are identifiers — in Clerk, in `Role` on both sides,
in every check. The labels exist only in the frontend (`ROLE_LABELS` in
`@app/auth`). A fork renames both, and the slugs in the Clerk dashboard too
([`setup/making-it-yours.md`](../setup/making-it-yours.md)).

**Every check compares `Role` values, never Clerk's strings.** One function on each side
turns the token's claim into a `Role` — `get_current_role()` in `account`, `getUserRole()`
in `@app/auth` — so a change of identity provider rewrites those two and no role check.

**Only the server may change an organization.** Inviting a member, removing one or
changing a role needs Clerk's secret key, which never reaches a portal. No route does it
yet; today it is done in Clerk's dashboard.

**A supplier is also a row**, linked to its portal contact — the link and its lifecycle
are in [`../data-model/supplier.md`](../data-model/supplier.md). `SupplierID` (§2) resolves it.

## 2. From token to decision

```
Clerk session token
  o.id   → request.state.org_id      AuthMiddleware: verifies, never blocks
  o.rol  → request.state.org_role    ("org:" stripped)
  sub    → request.state.clerk_id
     │
     ├─ CurrentUser     the user row, provisioned on first sight         401 if no valid token
     ├─ CurrentOrgId    user.org_id — the row, not the token            403 if none
     ├─ CurrentRole     org_role, or Clerk's membership API when absent  403 if none or unknown
     │    └─ require_role(...)  InternalUserRole, PMOnly, ReviewerRole, SupplierRole
     ├─ SupplierID      the supplier whose contact_id is this user      403 SUPPLIER_NOT_LINKED
     └─ ownership       e.g. UserConversation: the row exists and is the caller's   404 / 403
```

`AuthMiddleware` only reads the token. Every decision is a FastAPI dependency, so a route
states its own requirements in its signature and nothing is implied by where it is
mounted. All of them live in the module whose business they are and are exported from its
root: identity and role in `account`, `SupplierID` in `supplier`, ownership in the module
that owns the row.

**The claims are Clerk's session token's** — what it is, how it travels and what else it
carries are in [`authentication.md`](./authentication.md) §2. `AuthMiddleware` strips the
`org:` prefix with `removeprefix`, so an unprefixed role would still parse, where
`getUserRole()` on the web rejects one. Clerk always sends the prefix, so the two agree on
every real token ([`../TODO.md`](../TODO.md), **Authorization — strict role prefix on the
server**).

**The org comes from the user row**, not the token. JIT provisioning fills `org_id` from
Clerk's membership API when the token carries none, so once `CurrentUser` has resolved,
the row is the authoritative value.

**The role falls back to Clerk** when the token has no org context — an OAuth token from
Swagger's Authorize flow, for instance. The answer is cached per process for 60 seconds,
and the membership webhooks invalidate the entry on a role change or removal, so
revocation is immediate unless every delivery fails
([`server/docs/authentication.md`](../../server/docs/authentication.md), **In-Memory Caches**).

## 3. Where each rule is enforced

| Rule | Server | Portals |
|---|---|---|
| Signed in | `CurrentUser` on the route | `auth.protect()` in `proxy.ts` |
| Right portal for the role | — | `proxy.ts`: `isInternalRole` / `isSupplierRole`, else `/unauthorized` |
| Role may perform this action | `require_role(...)` on the route | `role === Role.*` from `useAppAuth()`, or `<Protect role="org:…">`, to hide what would be refused |
| Row belongs to the caller's tenant | `CurrentOrgId` passed to a repository that filters by it; the table carries `TenantMixin` | — |
| Row belongs to the caller | the module's ownership dependency (`UserConversation`) | — |
| Caller acts for this supplier | `SupplierID` | — |

**The server is the only enforcement.** Everything in the portals column decides what
renders. A request made outside the portal — `curl` with a valid token — meets exactly the
server column. So a portal check never replaces a server check; it saves a user from
clicking something the server would refuse.

**No route calls `require_role` yet.** The four guards exist and are exported, but every
current route is owner-scoped (conversations) or about the caller themselves (`/auth/me`):
a supplier token may call any of them and sees only its own data. The first route whose
data belongs to an organization needs both a guard and `CurrentOrgId`
([`../TODO.md`](../TODO.md), **Authorization — the first organization-scoped route**).

**Tenant scoping is a test, not a convention.** A table whose rows belong to one
organization carries `TenantMixin` (an indexed, non-null `org_id`), and every repository
method on it takes and filters by the org id. `tests/unit/models/test_tenant_tables.py`
fails on any table that neither carries the mixin nor sits in its allowlist with a reason
([`server.md`](./server.md) R7 and §9). No table carries the mixin yet:
`supplier` is allowlisted until its first write route
([`../data-model/supplier.md`](../data-model/supplier.md)).

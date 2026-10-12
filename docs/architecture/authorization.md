# Authorization — the user is the tenant, and where each check runs

Who may see and change what: the ownership boundary and the layer that enforces each rule
on the server and in the app. How a token is verified and a user provisioned is
authentication, and is in [`authentication.md`](./authentication.md). Setting up the Clerk
instance is [`setup/clerk.md`](../setup/clerk.md). This describes the system as it stands
and is kept current.

---

## 1. The model

**The user is the tenant.** Data is keyed by `user_id`, a foreign key to the `user` row.
There are no organisations, no roles and no admin flag: every signed-in user is equal and
sees exactly the rows they own. There is no tenant table and no tenant id of our own.

## 2. From token to decision

```
Clerk session token
  sub    → request.state.clerk_id     AuthMiddleware: verifies, never blocks
     │                                (any other claim, including a stale `o`, is ignored)
     ├─ CurrentUser     the user row, provisioned on first sight         401 if no valid token
     └─ ownership       e.g. UserConversation: the row exists, is not     404 with the module's
                        soft-deleted and is the caller's                  not-found code
```

`AuthMiddleware` only reads the token. Every decision is a FastAPI dependency, so a route
states its requirements in its signature and nothing is implied by where it is mounted.
Identity lives in `account` (`CurrentUser`); ownership of a row is the dependency of the
module that owns the row. `get_current_user` also sets `request.state.user_id`.

**A missing row, a soft-deleted row and another user's row answer the same 404** with the
same error code (`CONVERSATION_NOT_FOUND` for conversations) and a message that names no
user, so an id cannot be probed for existence.

**The claims are Clerk's session token's** — what it is, how it travels and what else it
carries are in [`authentication.md`](./authentication.md) §2.

## 3. Where each rule is enforced

| Rule | Server | App |
|---|---|---|
| Signed in | `CurrentUser` on every non-public route | `auth.protect()` in `proxy.ts`; `/sign-in` and `/sign-up` are public |
| Row belongs to the caller (list) | the repository query filters by `user_id` | — |
| Row belongs to the caller (single row) | the module's ownership dependency (`UserConversation`) | — |

**The server is the only enforcement.** `proxy.ts` only requires a session; it decides
what renders, nothing more. A request made outside the app — `curl` with a valid token —
meets exactly the server column.

## 4. Ownership is a test

**Ownership is a test, not a convention.** A table whose rows belong to one user carries
`UserOwnedMixin` (`app.models.base`: an indexed, non-null `user_id`), and every repository
method on it takes and filters by the user id.
`tests/unit/models/test_owned_tables.py` fails on any table that neither carries the mixin
nor sits in its `ALLOWLIST` with a reason; the only entry is `user`, the owner itself. CI
runs it in `.github/workflows/module-boundaries.yml` ([`server.md`](./server.md) R7 and
§9).

# Roadmap

Where the work stands, and in what order it happens. **This is the only file in the
repo that records progress.** Everything else records reasoning, and a document that
carries both goes stale in the half a reader cannot check.

- **A spec says why** — `.superpowers/specs/*.md`, while its change is in flight. In the
  PR that merges it, what lasts moves into the docs and the spec is deleted.
- **A plan says how** — `.superpowers/plans/*.md`. Its `- [ ]` checkboxes are the
  task-level ledger for its branch, and it is deleted in the same PR.
- **This file says where we are** — one row per change in flight, updated in the same
  commit (or the same PR) as the work that moves it.

**States:** `not started` → `in progress`, plus `deferred` and `blocked`, each with a
reason. A row is deleted in the PR that merges its change to `main`, not when its branch
is green. What shipped is in `git log`.

Links are relative to `docs/`.

---

## Open

| Change | State | Branch | Where it is specified |
|---|---|---|---|
| **Foundation** — single-tenant B2C base | in progress | `port/template` | `.superpowers/specs/2026-10-12-foundation-design.md` |
| **Backend modules** — transactions, CSV import, analytics, insights, finance agents | not started | — | [`product/prd-mvp.md`](./product/prd-mvp.md) |
| **Frontend** — finance pages on the generated client | not started | — | [`product/prd-mvp.md`](./product/prd-mvp.md) |
| **Cutover** — merge into `main`, retire legacy | not started | — | — |
| **WS7** — SSE stream disconnect handling | deferred — past the B2C fork, by decision on 14 Sep 2026 | — | [`TODO.md`](./TODO.md), **Server — the chat stream ignores a client disconnect** |

Everything else outstanding is in [`BUGS.md`](./BUGS.md) (wrong today) or
[`TODO.md`](./TODO.md) (deferred to the change that should make it). An item gets a row
here when someone picks it up.

### Ordering notes

The dependencies already recorded in those two files, gathered in one place:

- **The database role split comes before row-level security.** A role with `BYPASSRLS`
  ignores every policy ([`BUGS.md`](./BUGS.md), [`TODO.md`](./TODO.md)).
- **Before the first deploy behind Traefik:** `--forwarded-allow-ips`, or every caller
  shares one rate-limit bucket.

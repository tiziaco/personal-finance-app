# GDPR Erasure — Findings

**Status:** findings only. No decisions taken, nothing implemented from this doc.
**Date:** 2026-08-25 · **Re-checked:** 2026-08-27 (after WS4 Clerk webhooks)
**Purpose:** input to a future spec + implementation plan. Written during the WS3
auth-hardening branch, after `DELETE /api/v1/auth/me` was repaired (it had never
completed successfully — `anonymize_user()` nulled a `NOT NULL` column).

Related: [`gdpr-compliance-guide.md`](./gdpr-compliance-guide.md) (the current,
partly-misframed guide), [`authentication.md`](./authentication.md).

---

## How to read this

Findings are split by **when** they need addressing, not by severity:

- **Group A — live in this B2B template.** GDPR applies to B2B contact data:
  a named supplier employee's work email is personal data, and Art 17 applies
  to them. These are gaps today, independent of any B2C fork.
- **Group B — for the B2C fork.** Concerns that only bite, or bite much harder,
  when the data subjects are consumers.
- **Group C — framing / doc debt.**

### Re-check, 2026-08-27 (after WS4)

Every finding was re-verified against the code. **All ten still stand.** WS4
(Clerk webhooks) changed the erasure cascade's *structure* and *reach*, not its
coverage — nothing in it was aimed at these findings, and nothing in it closed
one.

| | Verdict |
|---|---|
| A1 pseudonymisation, not anonymisation | **Unchanged.** `anonymize_user()` (`app/modules/account/models.py`) is untouched: `user.id` survives, and every `conversation` row still points at it |
| A2 Langfuse retains content | **Unchanged, wider.** No masking, no deletion path; the cascade now fires from a second trigger that also skips Langfuse |
| A3 partial-failure split state | **Partly mitigated.** The new webhook path is retryable via svix; `DELETE /api/v1/auth/me` still is not |
| A4 silent mem0 failure | **Unchanged.** Still caught and logged at `factory.py:104-105` |
| A5 log retention | **Unchanged.** WS4 removed PII from specific webhook log lines; no retention policy was written |
| A6 32-bit `anonymous_id` | **Unchanged.** Still `self.id[:8]` |
| B1–B3, C1 | **Unchanged.** Out of WS4's scope entirely |
| C2 asymmetric user types | **Unchanged, sharper.** WS4 makes admin-initiated deletion reachable, but runs one flow for both user types |

What WS4 *did* change is the call graph these findings point into: checkpoint
deletion moved out of `BaseAgent` into
`app/agents/shared/checkpointing/postgres.py`, and the cascade moved out of the
route into `UserService.erase_user`. Line references below were updated to match;
the reasoning was not.

---

## The central correction

> **Article 17 does not require anonymisation. It requires erasure of personal
> data.**

Anonymisation is one route to compliance — if nothing personal remains, there is
nothing left to erase. *Actually deleting the data* is the other route, and it is
simpler. The current implementation picked neither cleanly: it does a partial
overwrite and calls the result anonymisation.

So the design question is **not** "how do we anonymise harder?" It is:

> Is there anything on the retained row we have an Art 17(3) legal basis to keep?

Today the answer is no. "Referential integrity" and "analytics" are engineering
conveniences, not legal bases. The retention that *would* be justifiable — which
supplier submitted which compliance document, and when — lives in a documents
table that does not exist yet.

### Two corollaries that are easy to get wrong

**Soft delete is not banned.** GDPR regulates outcomes, not techniques — it has
nothing to say about `deleted_at` columns. The real rule is that *soft delete
alone does not discharge an erasure request*, because storage is processing
(Art 4(2)) and the data is still there. Soft delete remains legitimate as a
staging step before hard deletion, under an Art 17(3) exemption, for suppression
lists — and Art 18 (restriction of processing) effectively *requires* it: when a
subject contests accuracy or objects, you must keep the data and stop using it.
Hard-deleting there would be the violation.

This means `SoftDeleteMixin`'s docstring (`app/models/base.py:43`) is a useful
developer heuristic but overstated as a legal claim. `Conversation` using it is
fine — the message content is hard-deleted from LangGraph and `name` is cleared,
so the retained row is metadata. A1's objection is the retained *link to a
person*, not the soft delete.

**There is no 30-day rule.** No number appears in the regulation. Art 17(1) says
erasure "without undue delay"; Art 12(3) separately gives one month to *respond
to the request*, which is a response deadline, not permission to hold the data
for a month. A grace window before hard deletion is an optional design choice
that needs disclosing — deleting immediately is fully compliant and simpler.
During any such window the account is deactivated: processing stops at day zero,
only storage continues.

Data under an Art 17(3) exemption is the exception, and carries its own
retention period set by whatever law created the exemption — unrelated to any
grace window.

---

## Group A — live in this B2B template

### A1. The end state is pseudonymisation, not anonymisation

`app/modules/account/models.py` (`anonymize_user()`) overwrites the PII fields but
leaves the record identifiable by reference.

What survives erasure:

| Table | Retained |
|---|---|
| `user` | `id` (UUID, **unchanged**), `clerk_id`/`email` rewritten *from* that id, `email_verified`, `created_at`, `updated_at`, `last_synced_at`, `anonymized_at` |
| `conversation` | one row per thread — `id`, `user_id` → the user row, `created_at`, `updated_at`, `deleted_at` (`name` cleared) |

Against the three cumulative tests (Art 29 WP Opinion 05/2014, carried into EDPB
Guidelines 04/2025):

- **Singling out — fails.** `user.id` remains a stable unique key for exactly one
  person. That is the definition of a pseudonym. Recital 26 states pseudonymised
  data *remains* personal data.
- **Linkability — fails.** Every conversation row still points at that key, so a
  signup date plus a timestamped activity series stays attached to one individual.
- **Inference — partially fails.** Tenure, volume and activity timing remain readable.

The content of the PII is genuinely gone and unrecoverable from the row — that
part works. The record is simply still personal data.

**Note:** the EDPB's 2025 Coordinated Enforcement Action on the right to erasure
specifically targeted controllers presenting this state as anonymisation.

Since the modules refactor, the conversation-name blanking is done by `conversation`'s
`USER_ERASING` handler, not by `anonymize_user()`.

### A2. Langfuse retains message content keyed by the surviving id — *highest impact*

`app/agents/shared/observability/langfuse.py:33` sets `langfuse_user_id: user_id`
on every LLM call. No masking is configured anywhere in `app/`, so Langfuse
receives full prompts and completions.

`delete_me` never touches Langfuse.

The consequence compounds A1: the retained `user.id` is not a dormant pseudonym,
it is a **live join key into a third-party store that still holds the person's
conversations verbatim**. This defeats any anonymisation claim on its own,
regardless of what the `user` row looks like.

Note the asymmetry: the cascade hard-deletes LangGraph checkpoints
(`app/modules/account/service.py`) — the correct instinct — while the same
message content sits in Langfuse untouched. WS4 widened the reach rather than
the coverage: `erase_user` now also runs from the `user.deleted` webhook, so a
dashboard-initiated deletion leaves Langfuse equally untouched.

Needs: a Langfuse deletion path (API or documented retention), or masking at
`create_graph_config`, or both.

### A3. Partial-failure ordering leaves accounts in a split state

`app/modules/account/router/auth.py` deletes from Clerk **first**, before any local work.
`delete_conversation_checkpoints`
(`app/agents/shared/checkpointing/postgres.py`) correctly propagates on failure —
but by then the Clerk account is already gone, the DB transaction rolls back, and
the caller gets a 500.

Result: identity deleted upstream, local record intact, no retry path (the user
can no longer authenticate to re-trigger the endpoint).

WS4 narrows this to the self-service route only. The same cascade now also runs
from the `user.deleted` webhook, and that path *does* have a retry path: it never
calls Clerk (the Clerk-side deletion is what produced the event), and a raised
exception returns non-2xx, so svix redelivers. An admin-initiated deletion is
therefore already retryable; `DELETE /api/v1/auth/me` is not.

Needs: either an idempotent/resumable flow, an outbox, or reordering so
irreversible external calls happen last.

### A4. mem0 deletion failure is silent

`app/agents/shared/memory/factory.py:104-105` catches and logs, then returns
normally. Erasure reports success while the extracted-fact memories remain.

Contrast with `delete_conversation_checkpoints`, which propagates. The two
erasure steps have opposite failure semantics for no stated reason — and on the
webhook path the difference is now load-bearing: only the propagating step earns
an svix redelivery.

### A5. Logs retain both identifiers with no retention policy

`app/api/middlewares/logging.py:39-40` binds `clerk_id`; `user_id` is bound after
provisioning. Every structured log line carries them. Nothing documents a
retention period, and erasure does not touch log storage.

Standard practice is a documented, time-limited retention — but it has to be
written down to count.

WS4 treated log PII as a live concern in the webhook path (dropping an email from
`webhook_user_created`, and constraint text from 409 bodies), but wrote no
retention policy. The gap is unchanged.

### A6. `anonymous_id` uses only 32 bits of the UUID

`app/modules/account/models.py:66` — `f"deleted_user_{self.id[:8]}"` feeds two `unique=True`
columns (`clerk_id`, `email`). Birthday collision at ~65k anonymised users, at
which point a second erasure raises `IntegrityError`.

Negligible at this product's scale, and not a compliance issue — but using the
full UUID costs nothing.

---

## Group B — for the B2C fork

### B1. Backups are unaddressed

No policy documented for erasure propagation into DB backups. Defensible with a
documented rolling-window policy; currently there is no policy at all.

### B2. Consumer-scale erasure volume

A B2C product gets erasure requests at a rate that makes the manual/partial-failure
posture in A3 untenable. Whatever the fork does, it likely needs to be a queued,
retryable job rather than an inline request handler.

### B3. The retention justification disappears entirely

In B2B there is at least a *prospective* legal basis for retaining supplier
document-compliance records (Art 17(3)(b)/(e)). A B2C chat product has no
equivalent, which makes hard delete the obvious default rather than one option
among three.

---

## Group C — framing and doc debt

### C1. `gdpr-compliance-guide.md` is titled "for B2C Applications"

This repo is the B2B SaaS template. The guide's title, its "B2C" framing
throughout, and its `Transaction`/`FraudRecord` examples are all aimed at the
wrong product. The *conclusions* mostly still hold — B2B contact data is
personal data — but the framing should follow the fork, not stay here.

### C2. The two user types are not symmetric — and the endpoint treats them as if they were

This is the design question that most affects any future spec.

| | Internal PM | Supplier contact |
|---|---|---|
| Likely processing basis | Employment / contract / legitimate interest | Contract, consent |
| Art 17 erasure right | **Weaker** — an employee generally cannot demand deletion of a work account while employed | **Strong** |
| Effect of self-deletion | Strips audit trail from a compliance platform | Expected behaviour |

`DELETE /api/v1/auth/me` currently applies one flow to both. A PM self-deleting
may conflict with retention obligations the platform exists to serve.

**Unresolved:** whether this becomes two flows, one flow with a role guard, or an
admin-mediated process for internal users. Needs a decision before designing the
erasure target state — it determines whether we build one path or two.

WS4 supplies the mechanism for the third option without taking the decision: an
admin deleting a user in the Clerk dashboard now triggers the same cascade via
`user.deleted`. So "admin-mediated" is already reachable — but it runs the
identical flow for both user types, which is exactly the symmetry this finding
disputes.

---

## Resolving the retained `user.id`

The blocker for hard delete is **not** `user.id` (a PK, necessarily non-nullable)
but `conversation.user_id`: NOT NULL, and its FK carries no `ondelete` clause
(`alembic/versions/20260411_1650_0c7838405158_initial_schema.py:52`). A
`DELETE FROM "user"` raises `ForeignKeyViolation` today. `Supplier.contact_id` is
already nullable and already nulled by the flow — that one is fine.

Five patterns are in production use:

| Pattern | Mechanism | Fits when |
|---|---|---|
| **Cascade** | `ON DELETE CASCADE` | Child rows have no value without the user |
| **Orphan** | nullable FK + `ON DELETE SET NULL` | Row needed for counts, owner is not |
| **Shared sentinel** | One "ghost" user row; all children repoint to it | Content must survive, author must not (GitHub `ghost`, Reddit `[deleted]`) |
| **PII vault** | All PII in one table; everything else holds an opaque id | Erasure = delete one vault row. Common in fintech/healthcare |
| **Crypto-shredding** | Per-user encryption key; destroy the key | Immutable stores, event logs, **backups** (see B1) |

### The key correction to the current design

**A production tombstone is *shared*, not per-person.**

`anonymize_user()` mints a new tombstone *per erased individual*, which is k=1 —
it singles out. GitHub's ghost user is **one row shared by everyone who ever
deleted an account**, so it is k=N and singles out nobody. Identical
"keep the FK valid" goal, opposite privacy outcome.

The fix is therefore not a better `anonymous_id` (A6) — it is not minting one per
person. Repointing `conversation.user_id` at a single shared ghost row keeps
every conversation row for analytics while removing both the per-person key and
the grouping that made those rows mutually linkable.

---

## Analytics and ML training

Recorded because the instinct to retain conversations for training is what makes
this ticket wider than it looks.

**Retaining conversation rows buys nothing trainable.** A `Conversation` row is
`id`, `user_id`, `name`, and timestamps (`app/modules/conversation/models.py:37-39`). The
messages are in the LangGraph checkpoint tables keyed by `thread_id`, hard-deleted
in `erase_user` (`app/modules/account/service.py`); `name` is cleared by `conversation`'s `USER_ERASING` handler,
not by the anonymisation step (A1). A post-erasure row contains no
text. Keeping it buys a row count and costs a retained per-person activity series.

**Training on a departed user's content is the thing Art 17 blocks.** Rules that
apply identically to B2B and B2C:

- Training is usually a *different purpose* from service delivery (Art 5(1)(b)),
  so it needs its own lawful basis and disclosure, established **up front**. It
  cannot be discovered at deletion time. Consent withdrawn → Art 17(1)(b) →
  erase. Legitimate interest → a departed user's Art 21 objection generally wins.
- **Already-trained models** generally need not be retrained, but EDPB Opinion
  28/2024 holds a model can itself contain personal data where it memorises and
  can regurgitate, and that unlawful training data can taint the model.
- **Truly anonymised data is out of scope** (Recital 26) — but free-text queries
  and posts resist anonymisation. Stripping `user_id` is nowhere near enough
  (cf. AOL 2006 search logs, Netflix Prize). Aggregates are genuinely fine.
- **Art 17(3)(d) statistical/research purposes** is narrower than it sounds:
  Recital 162 requires aggregate results *not used for measures or decisions
  regarding particular individuals*, which excludes analytics feeding
  personalisation.

**The architecture that delivers it:** build a de-identified training corpus
**at ingestion**, with its own lawful basis and disclosure, so erasure never
touches it. Retrofitting de-identification at deletion time does not work. This
is a separate design decision and does not belong in the erasure flow.

Note `mem0` extracts *facts about the user* — profiling, unambiguously personal
data, not salvageable as "analytics."

---

## Design options (not decided)

Recorded so the future spec starts from a shortlist rather than a blank page.

| Option | Shape | Trade-off |
|---|---|---|
| **1. Hard delete, aggregate first** | Increment counters in a non-personal stats table, then cascade-delete the `user` row and its `conversation` rows | Genuinely stops being personal data. Needs the stats table first. Destroys nothing trainable — there is no content in those rows |
| **2. Shared sentinel** | Repoint `conversation.user_id` at one ghost user; delete the real `user` row | Keeps every row for analytics *and* de-identifies. Best fit if "keep the rows" is firm |
| **3. Keep pseudonymised, justify it** | Stop calling it anonymisation. Document the Art 17(3) basis per retained field, add a retention window ending in hard delete | Honest and low-churn, but requires a legal basis that today does not exist |
| **4. Split by user type** | Supplier contacts → option 1 or 2. Internal PMs → retention under employment basis, admin-mediated | Matches C2's asymmetry. Most work; most defensible |

Options 1/2 and 4 compose — 4 is one of the first two plus a role branch.
Option 2 supersedes the earlier "cascade" recommendation wherever conversation
rows are wanted for analytics.

**Note:** whichever is chosen, A2 (Langfuse) must be solved independently. No
change to the DB row affects it.

---

## Open questions for the spec

1. C2 — one erasure flow or two? Blocks the rest.
2. Does Langfuse retention get solved by deletion-on-erasure, by masking content
   at source, or by not sending `langfuse_user_id` at all?
3. Is there a documents/compliance-records model coming that *does* need
   post-erasure retention? If so, its legal basis and retention period should be
   designed in, not retrofitted. This is also where sentinel + PII vault becomes
   the right pairing: the document survives for audit, the submitter does not.
4. What is the log retention window, and who enforces it?
5. Does A3 justify an outbox/job queue, or is reordering the external calls enough?
6. Is a de-identified training corpus wanted at all? If yes it needs a lawful
   basis, a privacy-policy disclosure, and an ingestion-time pipeline — none of
   which belong in the erasure flow. If no, say so explicitly so the question
   stops resurfacing.
7. Are conversation rows actually wanted post-erasure? They hold no content, so
   the honest answer may be no — which collapses option 2 into option 1.

---

## Verification notes

Findings were read from source on 2026-08-25 at commit `6c2532a`
(`feat/ws3-auth-hardening`). Anchors cited:

- `app/modules/account/models.py:44-56` — `User` fields
- `app/modules/account/models.py:58-75` — `anonymize_user()`
- `app/modules/conversation/models.py:38` — retained FK (`user_id`)
- `app/modules/supplier/models.py:19` — `contact_id` (nulled on erasure, correct)
- `app/modules/account/router/auth.py` — `delete_me` seven-step flow
- `app/agents/shared/observability/langfuse.py:23-37` — trace metadata
- `app/agents/shared/memory/factory.py:98-105` — swallowed exception
- `app/agents/shared/checkpointing/postgres.py:93-113` — checkpoint deletion (propagates)
- `app/api/middlewares/logging.py:37-40` — identifier binding

`grep -rn "mask" app/` returns nothing — no Langfuse content masking.

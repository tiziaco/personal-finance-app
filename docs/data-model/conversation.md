# Conversation — Data Model

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 13 Oct 2026
**Describes:** [`../product/features/chat.md`](../product/features/chat.md).
**Scope:** the `conversation` table — one row per chat thread with the assistant.
**Source of truth:** the code — `server/app/modules/conversation/models.py` and the Alembic
revision `0c7838405158`. The sketch below was last brought in line with them on
13 Oct 2026; where the two disagree, the code wins. Conventions: [`README.md`](./README.md).

---

## 1. Approach

**The row is the thread's metadata; the messages are not here.** They live in LangGraph's
checkpoint tables, keyed by the thread id, which is this row's `id`.

**A conversation belongs to one user**, and every read goes through that ownership
(`UserConversation`, [`../architecture/authorization.md`](../architecture/authorization.md) §3).

## 2. Schema sketch

```sql
CREATE TABLE conversation (
    id          UUID        PRIMARY KEY DEFAULT uuidv7(),   -- also the LangGraph thread id, as text
    user_id     UUID        NOT NULL REFERENCES "user" (id),
    name        VARCHAR     NOT NULL,                       -- '' until titled; blanked on erasure
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL
);
```

## 3. Indexes

| Index | Unique | Serves |
|---|---|---|
| `ix_conversation_user_id` | no | a user's conversations |
| `ix_conversation_deleted_at` | no | the `deleted_at IS NULL` filter on every list |
| `ix_conversation_created_at` | no | ordering by recency, newest first |

## 4. Decisions

- **D1 — soft delete, not anonymisation.** The row holds no personal data except `name`,
  which erasure blanks. The personal content is the messages, and erasure hard-deletes the
  checkpoints of every conversation the user owns, soft-deleted ones included
  ([`server/CLAUDE.md`](../../server/CLAUDE.md), **GDPR — Right to Erasure**).
- **D2 — `conversation` carries `UserOwnedMixin`; its `user_id` is the owner.**
- **D3 — titles are written on request.** An empty `name` means untitled. After a
  completed reply, the client calls `POST /conversation/conversation/{id}/title`. The
  server asks the model for a title of at most 6 words from the first exchange and saves
  it, capped at 100 characters. A named conversation, or one with no reply yet, is
  returned unchanged. A model failure leaves it untitled, and the next completed reply
  retries. Not generated in the stream, whose event shape is fixed.

## 5. Deferred

Nothing.

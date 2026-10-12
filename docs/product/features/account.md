# Account

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 12 Oct 2026
**Scope:** how a person signs up and in, the profile, and deleting an account — for the
people deciding scope and for agents working on it. This describes the account as a
product; how it works is architecture.
**Data model:** [`../../data-model/account.md`](../../data-model/account.md).
**Related:** [`../../architecture/authentication.md`](../../architecture/authentication.md)
(how signing in works) · [`../../architecture/authorization.md`](../../architecture/authorization.md)
(where each rule is enforced) · PRD [§2](../prd-mvp.md#2-account).

---

## 1. Signing up and in

Sign-up is public: anyone can create an account at `/sign-up`. A returning user signs in
at `/sign-in`, with a password or an email code.

There is no separate step to create the account on the platform: the first authenticated
request creates it, or Clerk's `user.created` webhook does, whichever comes first. A new
user lands in the app straight away.

There are no organisations and no roles. Every signed-in user is equal, and sees only
their own data.

## 2. The profile

Name, email and avatar are the identity provider's. The user edits them in Clerk's user
profile window, opened from the user panel's **Account** item, and the platform picks the
change up on its own.

## 3. Deleting an account

A user can delete their own account, or an operator can delete them from the identity
provider's dashboard. Both run the same erasure.

**What is erased:** the sign-in account and every session; the user's name, email and
avatar; their conversations with the assistant and the chat history in them; the
assistant's long-term memory of them. The user row itself is anonymised, so anything that
pointed at it still points somewhere.

**Finance data joins the cascade with each backend module.** Transactions, CSV mapping
profiles and insights are the user's, and erasing the account must erase them; each module
adds its tables to the cascade when it is built (sub-project 2).

**Open:** the target state is not decided. What erasure leaves today is pseudonymised
rather than anonymous, and the tracing service still holds conversations
([`../../TODO.md`](../../TODO.md), **Erasure**).

## 4. Open questions

- **Erasure's target state**, above.
- **Leaving without deleting.** Should a user be able to export their transactions before
  deleting? The legacy app had no export, and none is planned.

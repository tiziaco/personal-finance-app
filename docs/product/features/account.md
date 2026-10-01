# Account

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 29 Sep 2026
**Scope:** how a person gets in, organizations, the roles, the profile, and deleting an
account — for the people deciding scope and for agents working on it. This describes the
account as a product; how it works is architecture.
**Data model:** [`../../data-model/account.md`](../../data-model/account.md).
**Related:** [`../../architecture/authentication.md`](../../architecture/authentication.md)
(how signing in works) · [`../../architecture/authorization.md`](../../architecture/authorization.md)
(where each rule is enforced) · PRD [§2](../prd-mvp.md#2-account).

---

## 1. Getting in

A person joins by **invitation to an organization**, then signs in on the portal for their
role — the internal portal or the supplier portal. There is no separate account to create
on the platform: accepting the invitation is enough.

Sign-up is invitation-only: there is no way in without an invitation.

## 2. Organizations

**Each customer is an organization** — the tenant. A member works inside one active
organization at a time and sees only its data.

## 3. Roles

A member has one role in their organization. These four are the template's example
domain's; a fork renames them ([`../../setup/making-it-yours.md`](../../setup/making-it-yours.md) §4).

| Slug | Label (UI) | Portal | What it is for |
|---|---|---|---|
| `project_manager` | Project Manager | internal | Manages projects, suppliers, orders and document checklists; the only role that manages the organization's members |
| `reviewer` | Reviewer | internal | Document due diligence beside the PM; approves or rejects documents, creates nothing |
| `approver` | Approver | internal | The final check before payment; read-only |
| `supplier` | Supplier | supplier | An external company's contact; sees its own orders and uploads its own documents |

A member signs in on their role's portal. Someone on the wrong portal — or with no role
yet, partway through an invitation — lands on `/unauthorized`.

## 4. The profile

Name, email and avatar are the identity provider's. A member edits them in its profile
window, opened from the portal, and the platform picks the change up on its own.

## 5. Deleting an account

A member can delete their own account through the API (`DELETE /api/v1/auth/me` —
no portal screen calls it yet), or an admin can delete them from the identity
provider's dashboard. Both run the same erasure.

**What disappears:** the sign-in account and every session; the member's name, email,
avatar and organization on the platform's record; the names and messages of their
conversations with the assistant, and the assistant's memories of them; the link to the
supplier company they acted for.

**What stays:** an anonymised record, so anything that pointed at the member still points
somewhere.

**Open:** the target state is not decided. What erasure leaves today is pseudonymised
rather than anonymous, and the tracing service still holds conversations
([`../../TODO.md`](../../TODO.md), **Erasure**).

## 6. Open questions

None beyond erasure's target state, above.

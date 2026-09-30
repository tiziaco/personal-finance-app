# Suppliers

**Status:** draft · **Owner:** Tiziano · **Last updated:** 29 Sep 2026
**Scope:** supplier companies, their portal contact, and the documents they owe.
**Data model:** [`../../data-model/supplier.md`](../../data-model/supplier.md).
**Related:** [`account.md`](./account.md) (the `supplier` role) · PRD
[§3](../prd-mvp.md#3-suppliers).

---

## 1. This is the example domain

Supplier document compliance is the template's worked example. It shows what a feature doc
looks like before most of it is built. A fork replaces it
([`../../setup/making-it-yours.md`](../../setup/making-it-yours.md) §4).

## 2. Who

- **Internal project managers** manage suppliers, orders, document compliance and expiry
  tracking, with reviewers and approvers beside them ([`account.md`](./account.md) §3).
- **Each supplier company has one portal contact** — a user with the `supplier` role, who
  acts for that company.

## 3. What a supplier does

Upload the documents each order requires, track each one's submission status, and receive
notifications when something is due, rejected or about to expire. **Not built.**

## 4. What a project manager does

Maintain suppliers and orders, set the documents each order requires, and track review
and expiry. Reviewers approve or reject documents; approvers give the final check before
payment. **Not built.**

## 5. What is built

- The **supplier company record**: name, code and VAT number.
- The **link from a company to its portal contact**, made from the invitation when the
  contact is first provisioned, and cleared if they delete their account or leave the
  organization.

## 6. Open questions

Each has the default in place until it is decided.

| # | Question | Default |
|---|---|---|
| S1 | One portal contact per supplier, or several? | One |
| S2 | Who invites a supplier's contact? | A project manager |
| S3 | Which document types exist, and how does each expire? | None fixed; set per order |

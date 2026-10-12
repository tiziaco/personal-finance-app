# MVP — Product Requirements

**Status:** agreed · **Owner:** Tiziano · **Last updated:** 12 Oct 2026
**Scope:** what the first release does — a personal finance app for friends and family. The
legacy v1.0 app shipped it; the port rebuilds it on this repo's single-tenant base.
**Related:** [`../data-model/`](../data-model/) (what is stored) ·
[`../ROADMAP.md`](../ROADMAP.md) (where the port stands)

---

## 1. Scope

A personal finance app for friends and family. Each person signs up, uploads the CSV
exports their bank gives them, and gets categorised transactions, analytics on where the
money goes, and AI-written insights, plus an assistant they can ask about their own
finances. Sign-up is public, and each user sees only their own data.

The core promise: understand where your money goes — at a glance on the dashboard, in
depth through analytics and insights — with no data entry beyond uploading a CSV.

**Legacy and port.** The legacy v1.0 app (March 2026) shipped everything below except
budgets. This repo rebuilds it: the backend modules in sub-project 2, the finance pages
in sub-project 3. Each feature doc says what v1.0 did, which is what the port rebuilds.

**Not in this release:** connecting to a bank, more than one currency, households or
shared accounts, splitting a transaction across categories, email or push alerts,
exporting data. Each feature doc lists its own.

## 2. Account

Public sign-up, signing in, the profile, deleting an account:
[`features/account.md`](./features/account.md).

## 3. Transactions

Browse, search, filter, add, correct and delete transactions:
[`features/transactions.md`](./features/transactions.md).

## 4. CSV import

Upload a bank export, confirm the column mapping, import:
[`features/csv-import.md`](./features/csv-import.md).

## 5. Categorisation

How each transaction gets one of the fixed categories, and how the user corrects it:
[`features/categorisation.md`](./features/categorisation.md).

## 6. Analytics

The dashboard and the four analytics views:
[`features/analytics.md`](./features/analytics.md).

## 7. Insights

AI-written observations about the user's spending:
[`features/insights.md`](./features/insights.md).

## 8. Chat

The assistant the user can talk to: [`features/chat.md`](./features/chat.md).

## 9. Budgets

Not built, and out of scope for the port: [`features/budgets.md`](./features/budgets.md).

## Decisions

| # | Decision | Date |
|---|---|---|
| 1 | **The user is the tenant.** Data is keyed by the user; there are no organisations, households or shared accounts | 12 Oct 2026 |
| 2 | **Sign-up is public.** Anyone can create an account at `/sign-up`; there is no invitation | 12 Oct 2026 |
| 3 | **No roles.** Every signed-in user is equal; there is no admin | 12 Oct 2026 |
| 4 | **Another user's data looks like missing data.** Asking for someone else's transaction or conversation answers "not found", never "forbidden" | 12 Oct 2026 |
| 5 | **No legacy data is carried over.** The legacy app held dev and test data only | 12 Oct 2026 |
| 6 | **Budgets are out of scope for the port.** The legacy app only showed a "Coming soon" page | 12 Oct 2026 |

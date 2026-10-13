# Transactions

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 13 Oct 2026
**Scope:** the user's transactions — browsing, searching, filtering, adding, correcting and
deleting them. Legacy v1.0 shipped this; the port rebuilds it in roadmap step 2,
Transactions. Getting transactions in from a bank file is
[`csv-import.md`](./csv-import.md).
**Data model:** [`transaction.md`](../../data-model/transaction.md).
**Related:** [`categorisation.md`](./categorisation.md) · [`analytics.md`](./analytics.md) ·
PRD [§3](../prd-mvp.md#3-transactions).

---

## 1. Who and why

Anyone using the app. The transaction list is the reference view: where was that charge,
and is it filed under the right category? Because the categories are assigned by AI, the
user must be able to review and correct them, and to remove junk or duplicates.

## 2. What the user can do

- **Browse** their transactions in a paginated table (numbered pages, not infinite
  scroll), newest first. On a phone the table becomes a list of cards.
- **Search** by merchant (substring, case-insensitive).
- **Filter** by date range (shortcuts: today, this week, this month, last month, or a
  custom range), by category (one or several), by amount range and by recurring or not.
- **Sort** by date, amount or merchant, ascending or descending.
- **Add** a transaction by hand.
- **Edit** a transaction — date, merchant, amount, description, category, recurring.
- **Delete** a transaction, after confirming.
- **Act on many at once** (desktop): select rows and change their category, or delete
  them, up to 100 at a time. A bulk action is all or nothing: if one selected
  transaction is missing, none changes.
- **Delete all** of their transactions from Settings, permanently, after confirming.
- **Start from an empty state.** A user with no transactions sees a prompt to add a
  transaction (to upload a CSV once CSV import ships); a filter with no match offers to clear the filters.

## 3. The fields

A transaction has:

- a **date**;
- a **merchant** (required, 255 characters at most);
- an **amount** — a decimal with two places, up to twelve digits. Money out is negative
  and money in is positive; the analytics read the sign;
- a **description** (optional, 1,000 characters at most);
- the bank's **original category** (optional), kept as imported;
- a **category**, one of the fixed list in [`categorisation.md`](./categorisation.md);
- a **confidence** between 0 and 1 for how sure the categoriser was — 1 for anything the
  user entered or edited by hand;
- whether it is **recurring**.

The database also keeps an import fingerprint (see below) and the created and updated
times; the user never sees them.

## 4. Rules and edge cases

- **Amounts are decimals, never floats.** On the wire they are strings, so no precision is
  lost.
- **Currency is EUR.** The amount carries no currency. Settings offers EUR, USD, GBP and
  CHF, but that is a display preference kept in the browser: it changes the symbol, not
  the number.
- **Deletes are soft.** A deleted transaction is hidden from every list and every
  analytic, but its row stays.
- **Duplicates are recognised, not forbidden.** Each transaction gets a fingerprint from
  its user, date, merchant, amount and description. The import skips a row whose
  fingerprint already exists; adding one by hand that matches an existing transaction asks
  before it is saved.
- **Someone else's transaction is a missing one.** Asking for another user's transaction
  answers "not found".
- **Page size** is 20 by default and 100 at most.

## 5. Not built

Splitting one transaction across categories; multiple currencies; households or shared
views; inline row editing (the edit is a dialog on purpose); undo for a delete; exporting
transactions; a bank connection.

## 6. Open questions

- **Currency.** Is a display-only currency symbol worth keeping, or should the setting go
  until multi-currency is a real decision?
- **Undo.** Deletes are soft in the database, but nothing in the product restores one.
  Is "recently deleted" wanted?

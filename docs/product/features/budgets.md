# Budgets

**Status:** draft · **Owner:** Tiziano · **Last updated:** 12 Oct 2026
**Scope:** setting spending limits by category and tracking them. Not built, and out of
scope for the port.
**Data model:** none.
**Related:** [`analytics.md`](./analytics.md) · [`categorisation.md`](./categorisation.md) ·
PRD [§9](../prd-mvp.md#9-budgets).

---

## 1. Not built

The legacy app showed a **Coming soon** page on the Budgets route and had no backend. Out of
scope for the port: the port ships no Budgets page and no budget endpoints.

The legacy page promised what a later version would do: set spending limits by category,
track progress month by month, and warn when a limit is near.

## 2. Who and why

Someone who wants to spend less in a category and see how far along the month they are. It
builds on the categories and the monthly analytics that already exist.

## 3. Open questions

- **When, if ever.** The v1.0 research put budgets in "v2+", behind a backend change.
- **Shape.** A limit per category per month, or a single overall limit? Rolling over unused
  amounts?
- **Alerts.** Warnings need a notification channel, which the product does not have (it has
  no email or push).
- **Nav item.** Without the page, the sidebar has no Budgets entry.

# Analytics

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 12 Oct 2026
**Scope:** the numbers and charts computed from the user's transactions — the home
dashboard and the analytics page. Legacy v1.0 shipped this; the port rebuilds it (the
calculations in sub-project 2, the pages in sub-project 3).
**Data model:** pending — written with the backend module (sub-project 2). Analytics
stores nothing of its own: it reads [`transactions.md`](./transactions.md).
**Related:** [`insights.md`](./insights.md) · PRD [§6](../prd-mvp.md#6-analytics).

---

## 1. Who and why

Anyone with imported transactions. The app's promise is knowing where your money goes at a
glance (the dashboard) and in depth (the analytics page). Everything is computed from the
user's own transactions on request; nothing is entered.

## 2. What the user can do

**The dashboard** (the page after sign-in) shows:

- a welcome header;
- four summary cards: **Total Spent**, **Recurring Costs**, **Net Balance** and **Average
  Cashflow**;
- a pie chart of spending by category and a line chart of the monthly trend;
- the ten most recent transactions, linking to the full table;
- a callout with the top AI insights, linking to the insights page.

**The analytics page** has four tabs, each loaded the first time it is opened:

- **By Category** — spend per category, ranked, with each one's share of the total. A
  range of 1, 3 or 6 months (3 by default).
- **Income vs Expenses** — income and expenses by month, with a cash-flow summary.
- **Trends** — the monthly expense trend and month-over-month growth.
- **Seasonality** — spending by day of week and by month of year.

Every chart has a loading skeleton and an empty state, and fails on its own without taking
the page down.

## 3. What is measured

In product terms, the calculations cover:

- **Spending overview** — total income, total expenses, net, averages, monthly burn rate.
- **Categories** — top categories by spend, how often against how much, trend per category.
- **Merchants** — top merchants by spend and by frequency, and how concentrated the spending
  is in a few.
- **Recurring** — recurring expenses, likely hidden subscriptions, the monthly recurring
  cost.
- **Behaviour** — day-of-week patterns, seasonal sensitivity, and which categories are stable
  and which volatile.
- **Anomalies** — outlier transactions (a rolling z-score; default 2.5 standard deviations
  over a 30-day window) and recent category spikes.

All of them accept an optional start and end date.

## 4. Rules and edge cases

- **The sign of the amount decides.** Positive amounts are income, negative are expenses;
  deleted transactions are excluded.
- **Money is shown in EUR**, or the symbol the user picked in Settings; see
  [`transactions.md`](./transactions.md) on why that is display only.
- **Mobile.** The summary cards go two by two and the tables become card lists.
- **Dark mode** is supported throughout.
- Each page's data is cached in the browser for a time proportional to how costly it is to
  compute (30 seconds for transactions, up to 10 minutes for insights).

## 5. Not built

- **No screen for recurring, merchant concentration or anomalies.** The v1.0 backend
  computes them and the client has hooks for them, but no page shows them; only the
  seasonality tab uses the behaviour data. The anomalies and recurring figures reach the
  user through [insights](./insights.md).
- Stable-or-volatile badges; a custom date range on the analytics page; saving or sharing a
  view; exporting; drag-and-drop dashboard layout.

## 6. Open questions

- **Which of the unseen analytics deserve a screen?** Recurring subscriptions and anomalies
  were rated worth having in the v1.0 research (priority 2) and not built.
- **A savings rate.** The v1.0 research asked for a savings-rate card; the cards that
  shipped are different (above). Is a savings rate wanted?
- **Date range on the dashboard.** The dashboard has no range control; is "this month" the
  right default?

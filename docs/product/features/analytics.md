# Analytics

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 15 Oct 2026
**Scope:** the numbers and charts computed from the user's transactions — the home
dashboard and the analytics page. Legacy v1.0 shipped this; the port rebuilds it (the
calculations and the dashboard in roadmap step 5a, the analytics page in step 5b).
**Data model:** none — analytics stores nothing. It reads the user's active transactions
([`../../data-model/transaction.md`](../../data-model/transaction.md)) through one read path,
`transaction_service.list_for_analysis`.
**Related:** [`insights.md`](./insights.md) · PRD [§6](../prd-mvp.md#6-analytics).

---

## 1. Who and why

Anyone with imported transactions. The app's promise is knowing where your money goes at a
glance (the dashboard) and in depth (the analytics page). Everything is computed from the
user's own transactions on request; nothing is entered.

## 2. What the user can do

**The dashboard** (the page after sign-in) shows:

- a welcome header;
- four summary cards for the **reference month** — the latest calendar month holding a
  transaction, up to the current month (a future-dated row never takes the page over; if
  every row is in the future, the latest of them), named on the page ("September 2026"):
  **Total Spent**, that month's
  expenses; **Recurring Costs**, the expenses flagged recurring in that month and how many
  there were; **Net Balance**, income minus expenses; **Average Cashflow**, the mean
  monthly net over the three months to it (fewer when the data starts later; an empty
  month counts as zero);
- a donut of the reference month's top five categories plus Other, and a line chart of
  income and expenses over the six months to it;
- the ten most recent transactions, linking to the full table. With no transactions, the
  page shows an empty state linking to the transactions page.
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

How they compute, so the numbers can be checked:

- Money is a decimal string to the cent; every percent is on the 0–100 scale, to 2
  decimal places. A percent change, coefficient of variation or seasonal index with nothing
  to divide by is null, not zero. A share or an average of nothing is 0, beside the zero
  total or count it comes from. Months with no transactions are zero-filled in every series.
- A range covers 1900–2100. An explicit bound outside it is rejected; a transaction dated
  outside it is left out of every analysis.
- The sign decides; a zero amount is ignored by every sum, count and average.
- A merchant is its stored merchant key ([`data-model/transaction.md`](../../data-model/transaction.md)
  D7), so `PAYPAL *Spotify` and `Spotify` are one; it is shown under its latest spelling.
- Recurring is the stored flag, grouped by merchant. A merchant's monthly recurring cost is
  its median charge × charges ÷ months charged. A likely hidden subscription is an unflagged
  merchant charged 3 or more times a month on average, averaging 50 or less a charge.
- A category spike compares its last 30 days with its average 30 days over the rest of the
  range: flagged above 50%, and only when the rest holds at least 30 days.
- An outlier is an expense whose z-score against the individual expenses of the preceding
  `window_days` (its own day excluded) passes the threshold; it needs at least 5 such
  expenses and a nonzero spread. The top 20 are returned.
- Merchant concentration is the Herfindahl index over all merchants, 0–10000.
- Weekday and weekend spend are per real calendar day in the range.

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
- **Date range on the dashboard** — decided 15 Oct 2026: the latest month with data,
  labelled by name, not the calendar month (imports lag the calendar). A month picker is
  in [`TODO.md`](../../TODO.md).

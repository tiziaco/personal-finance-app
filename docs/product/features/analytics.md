# Analytics

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 16 Oct 2026
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
- four summary cards for the **reference month** — the latest *finished* calendar month
  holding a transaction, named on the page ("September 2026"). A row dated after the
  current month never takes the page over. A user whose only data is this month sees the
  month in progress instead, marked as such:
  **Total Spent**, that month's
  expenses; **Recurring Costs**, the expenses flagged recurring in that month and how many
  there were; **Net Balance**, income minus expenses; **Average Cashflow**, the mean
  monthly net over the three months to it (fewer when the data starts later; an empty
  month counts as zero);
- a donut of the reference month's top five categories plus Other, and a line chart of
  income and expenses over the six months to it (fewer when the data starts later);
- the month in progress, as **month-to-date** beside the cards: this month's income and
  expenses so far, against the same days of the previous month;
- the ten most recent transactions, linking to the full table. With no transactions, the
  page shows an empty state linking to the transactions page.
- a callout with the top AI insights, linking to the insights page.

**The analytics page** has four tabs, each loaded the first time it is opened:

- **By Category** — spend per category, ranked, with each one's share of the total and its
  change against the previous period. A range of 1, 3 or 6 months (3 by default).
- **Income vs Expenses** — income and expenses by month, with a cash-flow summary and the
  savings rate. A range of 3, 6 or 12 months.
- **Trends** — the monthly expense trend and month-over-month growth. A range of 4, 6, 12
  or 24 months.
- **Seasonality** — spending by day of week and by month of year.

Every range is made of **finished months**: the last N months before the one in progress,
and never earlier than the first month of data. The month in progress is shown apart, as
month-to-date. A user with no finished month yet sees the month in progress, marked
partial. Any whole number of months from 1 to 120 is accepted; the tabs offer the choices
above.

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

All of them accept either a number of months or an optional start and end date; giving
both is an error. Every response states the dates it covers.

How they compute, so the numbers can be checked:

- Money is a decimal string to the cent; every percent is on the 0–100 scale, to 2
  decimal places. A percent change, coefficient of variation or seasonal index with nothing
  to divide by is null, not zero. A share or an average of nothing is 0, beside the zero
  total or count it comes from. Months with no transactions are zero-filled in every series.
- Periods:
  - A period is whole calendar days over finished months. Without a range, it runs from the
    first month of data to the latest finished month holding data. A row dated after the
    current month is outside every period. With a number of months, it is the N months ending
    there, no earlier than the first month of data.
  - An explicit start or end is clipped to the months the data covers, and never goes past
    the current month. A range inside those months that holds no transactions is a period of
    zeros; a range wholly outside them, or a user with no transactions, is an empty period
    (no dates, zeros, no error).
  - A month is partial for three reasons only: an explicit date cuts it; it is the month in
    progress (its days end at the last transaction in it); or it is the first month of data
    and the first transaction falls after day 7 (its days start there). A past month whose
    import stopped early counts as whole, because the app cannot tell nothing happened from
    not imported. A month left with no days is dropped; a range with no days is empty.
  - Each month has a weight: 1 when whole, otherwise the days it covers over its length.
    Monthly averages are totals over the sum of the weights, so whole months divide by N and
    a partial month counts for the part it covers.
  - Month-over-month change, seasonality, stability and the growth halves use whole months
    only; a change touching a partial month is null. Every monthly series is zero-filled and
    marks partial months.
  - Month-to-date is the current month up to the last transaction in it, against days 1 to
    the same day of the previous month; a percent is null when the previous figure is 0.
    It does not depend on the period.
- Money is rounded half-up to the cent. The monthly burn rate is expenses minus income per
  month, so it is negative while the user saves; it is exactly the average monthly net with
  the sign reversed. The savings rate is net over income; null with no income. The latest
  month's percentages compare it with the period's average as shown, which includes it.
- A range covers 1900–2100. An explicit bound outside it is rejected; a transaction dated
  outside it is left out of every analysis. The CSV import rejects such a row instead of
  saving it; the bounds are `MIN_DATE`/`MAX_DATE` in `transaction/domain/dates.py`.
- The sign decides; a zero amount is ignored by every sum, count and average.
- A merchant is its stored merchant key ([`data-model/transaction.md`](../../data-model/transaction.md)
  D7), so `PAYPAL *Spotify` and `Spotify` are one; it is shown under its latest spelling.
- Recurring is the stored flag, grouped by merchant.
  - A merchant's billing rhythm is the median gap between its charges, in whole days (half
    rounded up).
  - From 25 days up, the cadence rounds to whole months, so 10 charged monthly costs 10.00 a
    month and 600 charged yearly costs 50.00. Below 25 days, the median charge is scaled to
    a month: charge × 30.436875 ÷ gap.
  - A single charge, or charges on the same day, spread the charge over the period's months
    and count as active.
  - A merchant has stopped when more than 1.5 times its gap has passed since its last charge,
    measured at the period's last day. The monthly recurring cost adds up the active
    merchants only.
- A likely hidden subscription is a merchant never flagged recurring anywhere in the user's
  history that is charged in at least 3 different months, with a median gap of 25 to 35
  days, every charge within 10% of the median, and a median of 50 or less. They are ranked
  by median charge × charges per month.
- Category growth compares the earlier half of the period with the later half, by each
  half's average monthly spend; with an odd number of whole months the middle one is left
  out, and fewer than 2 whole months gives nothing. The change is in euros, and the list is
  ranked by it. A category that falls to zero is -100%; one present only in the later half
  has no percent (it is new). The top five growing and top five declining are listed.
- Each ranked category also shows its spend in the previous period — the same length
  immediately before — and the change; both are null when no transaction falls there.
  Categories present only in the previous period are not listed.
- Stability is the coefficient of variation of a category's monthly totals, over whole months
  from its first month with spend; it needs 3 such months (stable below 0.3, moderate below
  0.7). The stable, moderate and volatile shares weight each category by its spend in the
  months judged.
- Seasonality by month of year uses whole months only; its index is that calendar month's
  average spend over the average of all whole months × 100. It reports how many months of
  each it rests on, so a page can say it has less than a year of data.
- A category spike compares its last 30 days of the period with its average 30 days from the
  period's start to those days, both inside the data. It is flagged above a 50% rise, and
  only when the increase is at least 5% of the period's average monthly spend. Spikes are
  ranked by the increase in euros. They are not checked with less than 30 days of baseline,
  and the response says so rather than reporting none.
- An outlier is an expense whose z-score against the earlier expenses of its own category
  in the preceding `window_days` (its own day excluded) passes the threshold; it needs at
  least 5 such expenses and a nonzero spread. Recurring expenses are neither candidates nor
  part of a window, and a window may reach back before the period. The top 20 are returned.
  Spikes still count recurring expenses.
- Merchant concentration is the Herfindahl index over all merchants, 0–10000.
- Weekday and weekend spend are per real calendar day in the period; the weekend bias is
  computed from unrounded daily spend.

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

- **No risk label on merchant concentration.** The old high-medium-low band used antitrust
  thresholds, and rent alone made anyone "high". The shares and the index remain.
- **No screen for recurring, merchant concentration or anomalies.** The v1.0 backend
  computes them and the client has hooks for them, but no page shows them; only the
  seasonality tab uses the behaviour data. The anomalies and recurring figures reach the
  user through [insights](./insights.md).
- Stable-or-volatile badges; a custom date range on the analytics page; saving or sharing a
  view; exporting; drag-and-drop dashboard layout.

## 6. Open questions

- **Which of the unseen analytics deserve a screen?** Recurring subscriptions and anomalies
  were rated worth having in the v1.0 research (priority 2) and not built.
- **A savings rate** — answered 16 Oct 2026: added. It is net over income, for the period
  and for each month, on the Income vs Expenses tab; not a dashboard card.
- **Date range on the dashboard** — decided 15 Oct 2026: the latest month with data,
  labelled by name (imports lag the calendar). **Reversed on 16 Oct 2026:** imports lag, and
  a month still in progress read as a collapse in spending. The standard is finished months,
  with the month in progress shown beside them as month-to-date; the reference month is the
  latest *finished* month with data, falling back to the month in progress only when there
  is no other. A month picker is in [`TODO.md`](../../TODO.md).

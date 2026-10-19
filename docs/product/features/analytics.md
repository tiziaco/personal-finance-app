# Analytics

**Status:** shipped · **Owner:** Tiziano · **Last updated:** 19 Oct 2026
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

- **By Category** — every category with spend, ranked as bars: its total, its share and
  its change against the previous period of the same length, named on the page ("compared
  with Apr – Jun 2026"). A category with a previous total but no percent reads "new"; with
  no previous period at all, the change reads "—". Below it, how often against how much (a
  table of purchases, average each and total per category, ranked by purchases) and the top
  10 merchants by spend. A range of 1, 3 or 6 months (3 by default); the totals are for the
  period.
- **Income vs Expenses** — above everything, the month-to-date strip: this month so far
  against the same days of the previous month. It hides when the period itself is the month
  in progress, since the chart already shows it. Then income and expenses by month as
  paired bars, the cash-flow summary (income, expenses and net for the period, each with its
  monthly average, and the savings rate), the latest month against the period average, and
  a monthly table with each month's savings rate. A range of 3, 6 or 12 months (6 by
  default).
- **Trends** — the spending trend by month with its 3-month average, the change from one
  month to the next, the savings rate over time, and the categories growing and declining
  (top five each: the monthly average in the earlier half of the period against the later
  half, the change in euros and in percent; "new" when there was no earlier spend,
  "stopped" when none is left). A range of 4, 6, 12 or 24 months (4 by default).
- **Seasonality** — all history, with no range, captioned with the months it rests on.
  The average spend per day of the week, with the purchases and average purchase behind
  it; weekdays against the weekend per day, with how much more or less a weekend day costs;
  and the month of year as an average, with its index against a typical month (35% above)
  and the number of years the average covers. A month with no data yet has no bar.

The open tab and, where a tab has one, its range are kept in the URL, so a reload or the
back button returns to the same view; a value the tab does not offer falls back to its default.

A partial month is named "so far" only when it is the month in progress (the month-to-date
month); any other partial month, such as a first month of data that starts late, reads "partial".

Every range is made of **finished months**: the last N months before the one in progress,
and never earlier than the first month of data. The month in progress is shown apart, as
month-to-date. A user with no finished month yet sees the month in progress, marked
partial. Any whole number of months from 1 to 120 is accepted; the tabs offer the choices
above.

Every chart has a loading skeleton, and a period change keeps the old figures, dimmed, while
the new period loads. Each request has one empty state and fails on its own:
one error card with a retry, in place of the charts that request feeds, without taking the
page down.

Rules that hold across the analytics page, for any change to it:

- The server computes every figure; the page fetches, formats and draws, and does no
  arithmetic on money or percents.
- A total is for a named period and an average says what it averages; no figure over all
  history stands in for a period, except Seasonality, which says it covers all history.
- A null percent reads "—", or a short reason ("no comparison yet"), never 0.
- Colour means good or bad, not direction: spending up and income down are bad. It always
  comes with an arrow or words.

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
    first month of data to the latest finished month holding data (or to the month in
    progress, when no finished month holds any). A row dated after the current month is
    outside every period. With a number of months, it is the N months ending
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
  - When the period has no whole month (the only data is the month in progress, or a part
    of one; a lone past month whose data starts after day 7; or an explicit date range
    inside one month), the average monthly income, expenses and net and the burn rate are null, and the
    Flow tab says "No full month yet". A part-month is never scaled up to a whole month. An
    empty period keeps 0.00.
  - Month-over-month change, seasonality, stability and the growth halves use whole months
    only; a change touching a partial month is null. The period's first month compares with
    the month before it, outside the period, when the data reaches there. Every monthly
    series is zero-filled and marks partial months.
  - Each month also shows a 3-month rolling average of expenses: that month and the two
    before it, reaching before the period; null when any of the three is partial or before
    the data.
  - Month-to-date is the current month up to the last transaction in it, against days 1 to
    the same day of the previous month. The response carries that day as `previous_through`
    (clamped to the previous month's length) and the month's `net`; the web shows them and
    works out neither. It is absent when the current month has no transaction. A percent is
    null when the previous figure is 0, and the comparison is blank when the previous month
    is only partly in the data (the data starts after its 1st); the previous figures are
    still shown. It does not depend on the period.
- Money is rounded half-up to the cent. The monthly burn rate is expenses minus income per
  month, so it is negative while the user saves; it is exactly the average monthly net with
  the sign reversed, and null when that is. The savings rate is net over income; null with
  no income. The latest month is the period's last whole month (none when it has none); its
  percentages compare it with the period's average as shown, which includes it.
- A range covers 1900–2100. An explicit bound outside it is rejected; a transaction dated
  outside it is left out of every analysis. The CSV import rejects such a row instead of
  saving it; the bounds are `MIN_DATE`/`MAX_DATE` in `transaction/domain/dates.py`.
- The sign decides; a zero amount is ignored by every sum, count and average.
- A merchant is its stored merchant key ([`data-model/transaction.md`](../../data-model/transaction.md)
  D7), so `PAYPAL *Spotify` and `Spotify` are one; it is shown under its latest spelling.
- Recurring is the stored flag, grouped by merchant. A merchant is listed when it has a
  flagged charge in the period; its charge count, months and median charge are the period's.
  - Charges on the same day are summed into one bill. A merchant's billing rhythm is the
    median gap between its billing days, in whole days (half rounded up), read from every
    flagged charge up to the period's last day — before the period too, so a one-month
    period still sees a yearly bill's year.
  - From 25 days up, the cadence rounds to whole months, so 10 charged monthly costs 10.00 a
    month, two charges of 10 on the same day each month cost 20.00, and 600 charged yearly
    costs 50.00. Below 25 days, the period's median bill is scaled to a month:
    bill × 30.436875 ÷ gap.
  - A merchant with one bill in all its history has no rhythm yet: the bill is spread over
    the period's months, but never over less than one (a first 10 this month costs 10.00),
    and it counts as active.
  - A merchant has stopped when more than 1.5 times its gap has passed since its last charge,
    measured at the period's last day. The monthly recurring cost adds up the active
    merchants only.
- A likely hidden subscription is a merchant never flagged recurring anywhere in the user's
  history, and not one the user has unticked on any charge, that is charged in at least 3
  different months of the period, with a median gap of 25 to 35 days, every charge within 10%
  of the median, and a median of 50 or less. They are ranked by median charge × charges per
  month.
- Category growth compares the earlier half of the period with the later half, by each
  half's average monthly spend; with an odd number of whole months the middle one is left
  out, and fewer than 2 whole months gives nothing. The change is in euros, and the list is
  ranked by it. A category that falls to zero is -100%; one present only in the later half
  has no percent (it is new). The top five growing and top five declining are listed.
- Each ranked category also shows its spend in the previous period — the same length
  immediately before — and the change; both are null when no transaction falls there, or
  when the data does not reach back over all of it (a shorter span would not compare).
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
  least 5 such expenses and a nonzero spread. When the category's window holds fewer than 5,
  the expense is scored against all one-off spending in the same window instead, so a large
  purchase in a thin category is still seen. The fallback never flags `atm` or
  `savings_investments` (money moved, not spent), though they still count in its window and its
  mean, nor any expense under 5% of the period's average monthly spend, the same floor spikes use. Each outlier says which it was compared
  with (`compared_with`: `category` or `all`). Recurring expenses are neither candidates nor
  part of a window, and a window may reach back before the period. The top 20 are returned.
  Spikes still count recurring expenses.
- Merchant concentration is the Herfindahl index over all merchants, 0–10000.
- Weekday and weekend spend are per real calendar day in the period; the weekend bias is
  computed from unrounded daily spend, and is blank when the period has no weekend days (or
  no weekdays).

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
  computes them and the client has hooks for them, but no page shows them. Top merchants
  have a screen, on the By Category tab; the anomalies and recurring figures reach the user
  through [insights](./insights.md).
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

# Analytics page — design

**Roadmap step:** 5b Analytics page · **Branch:** `feat/analytics-page` · **Date:** 16 Oct 2026
**Read with:** [`docs/product/features/analytics.md`](../../docs/product/features/analytics.md)
(§2–3 hold the measurement rules this page displays) and PR #16 (Analytics figures), which
added every server figure named below.

---

## 1. Intent

The home dashboard says where the money went last month. `/analytics` is where the user
digs in: which categories and shops take the money, how income and spending compare over a
few months, which way spending is heading, and when in the week and the year it peaks.

The legacy page answered those questions with misleading numbers. Spend by weekday was a
lifetime total per weekday. Month-of-year was a total across years, so a month present in
three years of data looked three times as big. The cash-flow summary was a lifetime sum with
nothing on screen saying so. Month-over-month growth skipped empty months and set the
half-finished current month beside full ones. Every figure on this page is therefore one of
two things:

- a total for a **named period**;
- an **average**, labelled with what it is an average of.

The server computes every figure (PR #16). The page fetches, formats and draws.

## 2. Goals, non-goals, anti-goals

**Goals**

- The four tabs below, each answering its question with honest, labelled figures.
- Every period visible on screen, by month name ("Jul – Sep 2026").
- Each section loads, empties and fails on its own.
- Works on a phone and in dark mode.

**Non-goals**

- A custom date range, saving or sharing a view, or exporting.
- Screens for recurring costs, anomalies or spikes: Insights (step 6) shows those.
- Merchant concentration, and stable-or-volatile badges.
- Category spend month by month. No route provides it.
- The dashboard's month picker.

**Anti-goals.** Any of these makes the page a failure even if it renders:

- A total over all history shown as if it were a period figure, or a total where the label
  implies an average.
- A month in progress drawn beside finished months as if it were one.
- Arithmetic on money or percentages in the browser (§4).
- Any edit under `apps/web/src/components/dashboard/`, `server/` or
  `packages/api-client/src/generated/`.

## 3. Constraints

- **Ownership (brief §3).** This step owns:
  - `apps/web/src/app/(dashboard)/analytics/`;
  - a new `apps/web/src/components/analytics/`;
  - the Analytics entry in `apps/web/src/lib/hub-nav.ts`.

  It may import from `components/dashboard/` (`SectionError`, `ANALYTICS_STALE_TIME`,
  `formatMonth`) but edits nothing there; step 6 is editing it. Nothing under `server/`.
  Nothing under the generated client.
- **Primitives.** Only primitives that already exist in `@app/ui`: `tabs`, `card`, `chart`
  (recharts), `table`, `skeleton`, `button`, `badge`, `tooltip`. Adding another goes
  through the coordinator first.
- **Sidebar order** (user, 16 Oct 2026): Home, Transactions, **Analytics**, Insights, Chat.
  Step 6 adds Insights after Analytics. On merge, keep both entries.
- Follow the `web-app-patterns` and `web-app-testing` skills.

## 4. Page-wide rules

**Periods.** Every period is made of **finished calendar months**, resolved by the server
from `months=N`:

- it ends at the latest finished month with data;
- it is never earlier than the first month of data;
- the page never sends `date_from`/`date_to`.

The page labels every period with **one shared helper** fed only by the echoed
`date_from`/`date_to`. It never reads the browser clock and never needs a `partial` flag,
which only spending carries.

- **Both ends on month boundaries** (`date_from` is a 1st, `date_to` a month's last day):
  "Jul – Sep 2026" for several months, "September 2026" for one.
- **Either end mid-month:** the label gives days at that end. This covers two cases:
  - the server's fallback to the month in progress, whose `date_to` is the last day with
    data: "1 – 16 Oct 2026";
  - a first month of data that starts mid-month: "12 – 30 Sep 2026",
    "12 Sep – 31 Oct 2026".
- **A shorter span than asked for** (the data starts later) is labelled as it really is.

Whether a date is a 1st or a month's last day is date formatting, not arithmetic, so it is
allowed. My call, after the builder check: telling the month in progress apart by the
browser's clock was rejected, because it can disagree with the server around midnight at a
month boundary.

Each tab has its own period choice. They don't share one:

| Tab | Choices | Default | Decided by |
|---|---|---|---|
| By Category | 1, 3, 6 months | 3 | user |
| Income vs Expenses | 3, 6, 12 months | 6 | choices: user; default: my call (shown in the mockup, not objected to) |
| Trends | 4, 6, 12, 24 months | 4 | user |
| Seasonality | none: all history | — | user |

**No arithmetic in the page** (user, 16 Oct 2026). The page may only:

- format money with the user's currency (the transactions module's `formatAmount`), and
  format months and percents;
- map category slugs to labels, as the dashboard does;
- parse decimal strings to numbers **for chart geometry only**, as the dashboard's
  `category-slices` does;
- choose colour, arrow and wording from the sign of a percent the server sent;
- choose wording from a null.

One display transform is my call and is flagged for review: Seasonality shows `index` 135
as "35% above a typical month" (§5.4). That is `index − 100`, a relabelling of one
server number.

**Nulls.** A null percent shows as "—", with a reason where one is short enough to fit
(e.g. "no comparison yet"). It is never shown as 0.

**Colour.**

- Income and expense series use the existing tokens `--chart-income` and
  `--chart-expense`.
- A change is coloured by whether it is good or bad, not by its direction:
  - spending up, or income down, is bad;
  - spending down, or income up, is good.
- An arrow and words always go with the colour, so colour is never the only signal.
- The exact tokens are the builder's call; they must work in both themes.

**Loading, empty, error.**

- Each section has its own skeleton and its own empty state.
- A failed query shows `SectionError` with a retry in place of only that section, as the
  dashboard does. A failed background refetch keeps the data already shown.
- Queries use `ANALYTICS_STALE_TIME` and `meta: { silentError: true }`.

**Tabs.**

- Use `@app/ui/tabs`.
- A tab's queries run only when it is first opened (feature doc §2). Opening it again
  reuses the query cache.
- The open tab and each tab's period are kept in the URL search params, so reload and back
  keep them (my call). There is one key per tab, so switching tabs never carries a period
  across:
  - `tab`: `category`, `flow`, `trends` or `seasonality`;
  - `category_months`, `flow_months`, `trend_months`.

  An unknown or unoffered value falls back to that tab's default. A default value is left
  out of the URL.
- **How:** `useSearchParams` and `router.replace(…, { scroll: false })` from
  `next/navigation`, in one small hook under `components/analytics/`.
  - `web-app-patterns` keeps nuqs behind `@app/data-table`, whose URL hook is shaped for
    lists (`page`, `ordering`, `search`).
  - That package is outside this step's ownership.
  - The skill's ban on `useSearchParams` applies to list components; this page isn't one.

**Mobile.**

- Tables become card lists.
- Charts go full width.
- The tab list must fit or scroll at 375 px, without the page scrolling sideways.

## 5. The tabs

Figures are named by the generated client's fields; `@app/api-client/types` is the
reference.

### 5.1 By Category

`useGetCategoryBreakdown({ months, top_n: 50 })` and
`useGetMerchantBreakdown({ months, top_n: 10 })`.

1. **Header.**
   - The period choice and the period label.
   - "Total spent" from `total_expenses`.
   - "compared with Apr – Jun 2026" from `previous_date_from`/`previous_date_to`, when
     they are non-null.
2. **Ranking.** Every category in `top_categories`, as ranked bars, not a pie (my call:
   the bars list every category, and bar length and percent agree). Each row shows:
   - the label;
   - a bar sized by `share_pct`;
   - `total`, and `share_pct`;
   - the change against the previous period, from `change_pct`:
     - an arrow, the percent and the good/bad colour;
     - **"new"** when `change_pct` is null but `previous_total` is non-null;
     - **"—"** when `previous_total` is null (no previous period).
3. **How often vs how much.** A table from `by_frequency`, which the server ranks by count:
   category, `count`, `average` (labelled "average each", per transaction) and `total`.
   A table, not a scatter plot (my call).
4. **Top merchants.** `top_by_spend` (10): merchant (latest spelling, as the server sends
   it), `count`, `total` and `share_pct`.

The tab's empty state shows when `total_expenses` is 0 or the period is empty
(`date_from` null). The merchants section has its own empty and error states.

### 5.2 Income vs Expenses

`useGetSpending({ months })`.

1. **Month-to-date strip** (user). It sits above the cash-flow summary and doesn't depend
   on the period choice. It is hidden when `month_to_date` is null. It reads:

   > **October so far (1–16 Oct)** · Spent €1,020.00, 8.2% less than 1–16 Sep · Income
   > €3,200.00, 1.6% more than 1–16 Sep

   - The day range comes from `through`; the comparison month from `previous_month`.
   - The figures are `expenses`/`expenses_change_pct` and `income`/`income_change_pct`.
   - A null percent reads "no comparison yet".
   - It never appears in the chart or the totals.
   - It is also hidden when the period itself is the month in progress, i.e. when
     `months[]` holds an item whose `month` equals `month_to_date.month` (the server's
     fallback when no finished month has data). Otherwise it would repeat the chart.
     This is a string comparison, with no clock (my call).
2. **Chart.** Grouped bars of `months[].income` and `months[].expenses`. A month with
   `partial` true is drawn lighter and marked "so far" in its tooltip.
3. **Cash-flow summary** (user):
   - `total_income`, `total_expenses` and `net` for the period;
   - each one's monthly average under it: `average_monthly_income`,
     `average_monthly_expenses`, `average_monthly_net`;
   - the period's savings rate, `savings_rate_pct` ("kept 33.1% of income"; "—" when null).
4. **Latest month vs average** (user). From `latest_month` (the period's last whole month);
   hidden when null. It shows income and expenses, each with `income_vs_average_pct` /
   `expenses_vs_average_pct` as "▲ 12.0% above your 6-month average", coloured good or bad.
5. **Monthly table.** Per `months[]`: month, income, expenses, net and `savings_rate_pct`.
   On a phone it becomes a card list. The per-month savings rate is here because the
   feature doc §6 places it on this tab.

### 5.3 Trends

`useGetSpending({ months })` and `useGetCategoryBreakdown({ months, top_n: 1 })`. The
growth lists are always the top 5, whatever `top_n` is (`TREND_SIZE` in
`server/app/modules/analytics/domain/categories.py`). The spending query is the same one
Income vs Expenses uses when the months match, and shares its cache.

1. **Spending trend.** Bars of `months[].expenses`, with a line of
   `months[].expenses_rolling_avg_3m` ("3-month average"). The line breaks where it is null.
2. **Month-over-month change.** Bars of `months[].expense_change_pct` around a zero line:
   above zero means spent more, coloured as bad. Null leaves a gap, with "—" in the tooltip.
3. **Savings rate.** A line of `months[].savings_rate_pct`, which breaks where null, with
   the period's `savings_rate_pct` as a headline.
4. **Growing and declining categories** (user). Two lists, `top_growing` and
   `top_declining`, top 5 each. Each row shows:
   - the category;
   - `earlier_monthly_average` → `later_monthly_average` ("per month");
   - `change_amount`, and `change_pct`:
     - **"new"** when `change_pct` is null;
     - "−100%" reads "stopped".

   The server ranks by the change in €. The caption reads "earlier half vs later half of
   the period, per month". The halves' dates are not echoed, so the caption names no
   months (my call).

Trends repeats the savings rate from Income vs Expenses on purpose: there it is a figure
for one period, here it is a direction over up to 24 months.

### 5.4 Seasonality

`useGetBehaviour()`, with no params: all history.

1. **Caption.** "Based on Mar 2024 – Sep 2026", from `date_from`/`date_to`.
2. **By day of week.** Seven bars of `by_weekday[].per_day`, labelled "average per day",
   Monday first. The tooltip or a small table under it shows:
   - `count`: purchases;
   - `average`: average purchase;
   - `days`: how many such days the average covers.

   This makes "Saturdays: fewer purchases, but bigger ones" visible.
3. **Weekdays vs weekend.** `weekday.per_day` and `weekend.per_day` side by side, with a
   sentence from `weekend_bias_pct` ("Weekend days cost you 23% more than weekdays"). The
   sentence is hidden when the value is null.
4. **By month of year.** Twelve bars of `seasonality[].average_spend`, labelled "average".
   - Each month shows `index` as above or below a typical month (§4 flags this transform).
   - The tooltip says how many years the average covers, from `years` ("average of 2
     Decembers").
   - A month with `years` 0 has no bar and reads "no data yet".

The tab's empty state shows when `date_from` is null.

## 6. Navigation

`/analytics`, in `HUB_NAV` after Transactions. The icon is the builder's choice from
`lucide-react`, e.g. a chart icon. The page title and route-level `loading.tsx` follow the
`/transactions` and `/home` routes.

## 7. Left to the builder

- The component breakdown inside `components/analytics/`, and the file names.
- The chart details within the rules above: axes, compact number format and tooltips.
- The exact good/bad colour tokens and the partial-month styling.
- The period selector's control, built from existing primitives.
- Copy, beyond the strings fixed above.
- Tests, per `web-app-testing`. At least these are covered:
  - each null and "new" display;
  - the period label, including partial and shortened spans;
  - lazy tab loading;
  - URL state falling back to defaults;
  - one section failing while the others render.

## 8. Docs at the end (brief §4)

In the PR that completes this:

- update `analytics.md`:
  - §2: each tab's contents as built;
  - §5: merchants now have a screen, concentration still doesn't;
- add a `TODO.md` entry: income and expense decided by sign alone (refunds count as
  income; savings transfers and ATM withdrawals as spending) — found in the legacy audit,
  out of scope here;
- set the roadmap row to `complete` with the PR link;
- delete this spec and its plan.

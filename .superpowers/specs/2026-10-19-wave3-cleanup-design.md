# Wave 3 cleanup — design

Roadmap row **Wave 3 cleanup**, branch `feat/wave3-cleanup`, PR into `template-base`.
Sources: `docs/TODO.md` **Wave 3 cleanup — shared analytics plumbing** (with its "Folded in"
paragraph), **Web — tests the suite does not have yet** (the retry rule only);
`docs/BUGS.md` **The server-status dot pings "healthy" while it shows an error**, **A test that
trips a rate limit gets a 500, and limits leak between tests**.

## 1. Intent

Pay down what the 5b and 6 reviews found before step 7 builds on analytics. Today every
`AnalyticsService` method reloads the user's whole history and reads its own clock, and
`insights/figures.py` calls about eleven of them per generation and reshapes untyped dicts.
Step 7's chat tools would add more callers of the same shape. The "same days of the previous
month" rule exists in four places, two of them in the browser, and they disagree at month ends.

The step changes **no behaviour except one rule** (§4): a period with no whole month has no
monthly average. Everything else is structure, two loading fixes and three small folded-in
bugs/tests.

**Success:** an insights generation loads the user's rows once and reads today once; the
month-to-date comparison window and net are computed only in `domain/spending.py`; the Flow tab
never shows a "/ month" figure larger than a part-month total; the folded-in bugs are fixed
with tests that failed first.

## 2. Goals

### Server

1. **One history load per caller.** A new way to load a user's usable rows and today once and
   then compute any analysis over any window in memory, returning the existing typed response
   models. The existing per-route service methods keep their signatures and become "load, then
   compute" over it, so routes and their tests do not change.
2. **Insights onto it.** `insights/figures.py` loads once and derives every window from the
   loaded data: reference month (`months=1`), the usual (`months=BASELINE_MONTHS + 1`, which
   `resolve_period` already clips to the first month with data), the spike window
   (`max(usual months, 2)`), and the month-to-date and same-days-previous ranges. Delete
   `_usual_months`, `_month_index` and `_same_days_previous_month`, and the second `spending`
   call they forced. The agent's input (`InsightsInput.figures`) is produced from typed models
   and stays the same JSON for the same data (modulo the new fields in goals 3 and 4).
3. **Month-to-date in one place.** `MonthToDate` / `MonthToDateResponse` gain
   `previous_through: date` (the last day of the previous month's comparison window, clamped to
   that month's length — already computed in `month_to_date`) and `net: Decimal`
   (income − expenses, server-side `Decimal`). Insights reads `previous_through` instead of its
   own copy.
4. **The no-whole-month average** (§4).
5. **Rate-limit fixture.** An autouse fixture in `server/tests/conftest.py` sets
   `app.state.limiter = limiter` and calls `limiter.reset()` before every test, whatever client
   fixture the test uses. Plus the reproduce test from BUGS.md — `renameConversation` called
   once more than its `CHAT` limit allows, asserting the last call is a 429 — written first and
   seen to fail with the 500. The count is read from `settings`, not hard-coded: BUGS.md says
   30, but `server/.env.test` sets `RATE_LIMIT_CHAT` to 100 a minute, so under test it is 101
   calls (*my call:* keep the test on this authenticated, per-user route rather than a cheaper
   IP-keyed one).

### Web

6. **Month-to-date copies deleted.** `month-to-date-card.tsx` drops its date arithmetic for the
   previous window, its browser-side net (`Number(...)` float maths) and the `unsigned` regex;
   it renders `previous_through` and `net` from the server. `month-to-date-strip.tsx` drops its
   day range for the previous month and uses `previous_through` (which fixes the unclamped
   31st-against-a-30-day-month case). The days-in-month progress bar stays: it is about the
   current month and is display, not a comparison rule.
7. **url-state exports.** Export `useQueryStates` and the number-literal parser from
   `@app/data-table/url-state`, and have `/analytics` (`use-analytics-params.ts`) use them
   instead of reaching around them.
8. **`ANALYTICS_STALE_TIME`** moves out of `components/dashboard/home-dashboard.tsx` into a
   plain module with no component imports; both the dashboard and
   `components/analytics/query.ts` import it from there.
9. **Shared chart props** between `components/analytics/` (`chart-parts.tsx`) and
   `components/dashboard/trend-chart.tsx`: the trend chart uses the shared margin, grid, axis
   and tooltip props rather than its own copies.
10. **Income vs Expenses (Flow tab) skeleton** gets blocks of the same height as the
    month-to-date strip and the latest-month section, so the page no longer shifts ~100 px
    (CLS 0.15) on load. The strip's block is hidden when the period is the month in progress,
    as the strip itself is.
11. **`keepPreviousData`.** `ANALYTICS_QUERY` in `components/analytics/query.ts` adds
    `placeholderData: keepPreviousData`, so picking an uncached period keeps the old figures
    instead of flashing every skeleton. While placeholder data is shown, the tab's content is
    dimmed and marked busy.
12. **Server-status dot.** `ServerStatusIndicator` draws the pulsing ring only under the same
    condition as green: no `error` and `status.status === "healthy"`. A test for stale healthy
    data plus an error, written first and seen to fail.
13. **`QueryProvider` retry test.** A 4xx is not retried; a 5xx is retried once; a failed
    refetch behind data already shown does not toast. Tests only. The current `retry` and
    `onError` in `packages/api-client/src/query-provider.tsx` already appear to do all three; if
    a test fails anyway, stop and bring it to the user rather than change the behaviour.

## 3. Non-goals

- **Caching rows across requests** — `docs/TODO.md` already has its own entry, which comes
  after this step. This step fixes the fan-out inside one caller only.
- **Promoting `Section`, `Change`, `PeriodSelect` to `@app/ui`.** The TODO makes it conditional
  on a second screen wanting them; none does yet. The bullet stays in `TODO.md`.
- **Any outlier, recurring or hidden-subscription rule, and anything in the `transaction`
  module** — those belong to Analytics rules.
- **The partial *first* month's weighting.** A period whose first month starts after day 7
  still counts that month by its days covered, as today. Only the "no whole month at all" case
  changes.
- A pace / projection figure ("on pace for €X this month"). Possible later, as its own feature.
- The failed-conversation-create test (step 7).

## 4. The one rule change: no monthly average without a whole month

**Decided by the user (19 Oct 2026):** do not scale a part-month up to a whole month. When the
only data is the month in progress, the Flow tab showed "€4,118.25 / month" against a
€2,125.55 period total.

**Rule:** when the resolved period has **no whole month** (`period.whole_months()` is empty),
`average_monthly_income`, `average_monthly_expenses`, `average_monthly_net` and `burn_rate` are
`null`. Otherwise they are unchanged (totals over the sum of month weights).
*Builder's note — my call:* the rule is "no whole month in the period", not "the period is the
month in progress", so it also covers a period that is a single partial past month (data began
after day 7 of the only month asked for) and an explicit date range shorter than a month. Both
are the same part-month scale-up. `burn_rate` goes null with them because it is defined as the
average monthly net with the sign reversed (`analytics.md` §3). `latest_month` is already null
in exactly this case.

- **Schema:** the four fields become `Optional[Decimal]`, with descriptions saying when they
  are null. The generated client follows via `make gen-contract`, never by hand.
- **Flow tab:** `Figure`'s average line, when the average is null, reads **"No full month yet"**
  in muted text instead of "€X / month" (*my call on the wording*). The totals and the
  month-to-date strip show as today.
- **Insights:** the spending figures then carry `null` averages when the reference month is the
  month in progress; the prompt already says a user with one month has no usual. No prompt
  change expected; the builder checks the prompt reads a null average correctly.
- **Docs:** `analytics.md` §3's averaging bullet and the burn-rate bullet gain the null case.

## 5. Constraints

- **Ownership conditions** (from the brief, binding on this branch): do not modify
  `analytics/domain/anomalies.py`, `analytics/domain/recurring.py` or anything under
  `server/app/modules/transaction/`. This branch is the only one that edits
  `server/tests/conftest.py`. Construct `AnalysisRow` only with its current fields (the rules
  branch may add defaulted ones). Never hand-edit `server/openapi.json` or the generated
  client; run `make gen-contract`.
- **No behaviour change** outside §4 — the insights input for the same data is the same JSON
  apart from the new `previous_through`/`net` fields and the §4 nulls. A characterisation test
  of `gather_figures` against seeded data, written before the rewrite, is the guard.
- The loaded bundle is **shaped for a second caller** (step 7's tools): typed, loads rows and
  today once, computes any window on demand, and lives in `analytics` behind its public API
  (`app/modules/analytics/__init__.py`), so `insights` and later `conversation` import it the
  same way `analytics_service` is imported today. Module-boundary import contracts must pass.
- Server conventions per the `server-patterns` and `server-testing` skills; web per
  `web-app-patterns` and `web-app-testing`.

## 6. Left to the builder

- The bundle's name and exact shape (a loaded object with one method per analysis taking a
  `DateRange`, or similar), and whether the existing route methods delegate to it or share a
  private helper — as long as goal 1's constraints hold.
- Where the plain `ANALYTICS_STALE_TIME` module lives.
- Which chart props are actually shared (goal 9): share what is identical; leave what differs
  on purpose.
- How the Flow skeleton knows the period is the month in progress before the first response
  (goal 10), e.g. from previous data or the dashboard's cached `reference_partial`; if nothing
  is known, show the block.
- How the dimming in goal 11 is applied (once in `QueryGate`, or per tab).

## 7. At the PR

Per `CLAUDE.md` and the brief: `analytics.md` §3 gets the §4 rule and the two month-to-date
fields; the architecture notes for the loaded bundle go where analytics' architecture is
documented; the closed `TODO.md` bullets and the two `BUGS.md` entries are deleted (the
`Section`/`Change`/`PeriodSelect` bullet stays); the roadmap row is set to `complete` with the
PR link; this spec and the plan are deleted.

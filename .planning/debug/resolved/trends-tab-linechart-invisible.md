---
status: resolved
trigger: "Investigate why the LineChart is not visible in the TrendsTab component"
created: 2026-03-01T00:00:00Z
updated: 2026-03-01T00:00:00Z
---

## Current Focus

hypothesis: get_spending_summary returns overview.stats with wrong shape — columns are ["metric","value"] not per-month rows — so stats is always empty or misread, triggering the empty-state guard
test: traced full data path from API -> service -> analytics tool -> frontend component
expecting: confirmed — root cause identified, no fix applied (diagnose-only mode)
next_action: return diagnosis

## Symptoms

expected: TrendsTab renders a LineChart showing monthly expense trends
actual: TrendsTab renders "No trend data yet" empty state — the LineChart branch is never reached
errors: none visible (silent data mismatch)
reproduction: navigate to Trends tab; useSpendingAnalytics({}, true) fires with no date_from filter
started: unknown — likely since initial implementation

## Eliminated

- hypothesis: API default date window excludes Oct/Nov 2025 data
  evidence: TransactionService.load_dataframe has no default date window; with None filters it fetches ALL user transactions
  timestamp: 2026-03-01

- hypothesis: useSpendingAnalytics disabled or not firing
  evidence: hook receives enabled=true and filters={}, React Query fires immediately; no issue in hook
  timestamp: 2026-03-01

- hypothesis: LineChart component crashes or renders invisibly
  evidence: LineChart is well-formed; it is never reached because stats.length === 0 causes the empty-state guard to short-circuit
  timestamp: 2026-03-01

## Evidence

- timestamp: 2026-03-01
  checked: web-app/src/components/analytics/trends-tab.tsx lines 52-62
  found: component reads data?.data as SpendingAnalyticsData, then accesses narrowed?.overview.stats ?? [] and guards on stats.length === 0
  implication: if stats is an empty array OR has the wrong shape, the LineChart is never rendered

- timestamp: 2026-03-01
  checked: server/app/tools/financial.py get_spending_summary() lines 57-66
  found: calls calculate_spending_overview() then uses overview["summary"].to_dicts() as the value for "stats"
  implication: the content of overview["summary"] determines whether stats has useful rows

- timestamp: 2026-03-01
  checked: server/app/analytics/descriptive.py calculate_spending_overview() lines 179-188
  found: "summary" is a flat two-column DataFrame with schema {"metric": Utf8, "value": Float64} containing exactly 5 aggregate rows: total_income, total_expenses, net_amount, total_transactions, avg_transaction_amount
  implication: overview["summary"].to_dicts() produces [{"metric": "total_income", "value": X}, ...] — NOT an array of per-month objects with {month, total_expense, total_income, net, expense_mom_growth}

- timestamp: 2026-03-01
  checked: web-app/src/components/analytics/trends-tab.tsx SpendingAnalyticsData interface lines 12-33
  found: interface declares overview.stats as Array<{month, total_expense, total_income, net, expense_mom_growth}> — a per-month shape
  implication: the TypeScript type is correct for what the frontend WANTS, but the backend "summary" DataFrame has a completely different shape

- timestamp: 2026-03-01
  checked: server/app/analytics/temporal.py calculate_monthly_spending_trend() lines 238-254
  found: with include_income=True the monthly_trend DataFrame has columns: year, month, month_name, total_income, total_expenses, net_amount, expense_mom_growth — this IS the per-month shape the frontend expects
  implication: the per-month data exists in trends["monthly_trend"], but get_spending_summary() maps it to recent_trend.last_3_months (only last 3 rows), not to overview.stats

- timestamp: 2026-03-01
  checked: server/app/tools/financial.py get_spending_summary() lines 64-71
  found: result dict maps overview["summary"].to_dicts() -> "overview.stats" and trends["monthly_trend"].tail(3).to_dicts() -> "recent_trend.last_3_months"
  implication: the full monthly_trend is discarded; overview.stats receives the flat aggregate metrics dict instead of per-month rows

## Resolution

root_cause: >
  get_spending_summary() (server/app/tools/financial.py) maps the wrong DataFrame to overview.stats.
  calculate_spending_overview() returns a flat aggregate "summary" with schema {metric, value} (5 scalar rows),
  but TrendsTab expects overview.stats to be an array of per-month objects with fields
  {month, total_expense, total_income, net, expense_mom_growth}.
  The per-month data lives in calculate_monthly_spending_trend()'s monthly_trend DataFrame
  but is only partially exposed as recent_trend.last_3_months (tail 3).
  Because the actual stats rows have no "month" key, the frontend TypeScript cast silently
  produces objects with wrong keys; none match the chartData mapping
  (s.month, s.total_expense), so chartData ends up as [{month: undefined, total_expense: undefined}...].
  However, more likely the 5-row flat summary IS serialised to dicts and stats.length is 5 (non-zero),
  so the LineChart IS rendered — but with no valid x/y values (month=undefined, total_expense=undefined),
  which means Recharts renders an empty/invisible line.
  OR if the type assertion causes a runtime access on a missing key with undefined result,
  Polars' .to_dicts() on the summary DF with columns ["metric","value"] will yield dicts like
  {metric:"total_income", value:1234} — none of which have a "month" or "total_expense" field,
  so every data point in Recharts is {month: undefined, total_expense: undefined},
  causing the line to not render.

fix: ""
verification: ""
files_changed: []

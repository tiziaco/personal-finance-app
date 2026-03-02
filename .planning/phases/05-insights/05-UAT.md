---
status: diagnosed
phase: 05-insights
source: 05-01-SUMMARY.md, 05-02-SUMMARY.md
started: 2026-03-02T08:50:00Z
updated: 2026-03-02T09:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Sidebar nav shows Insights entry
expected: The sidebar navigation includes an "Insights" item with a Lightbulb icon that links to /insights. It should be visible alongside other nav items like Home, Transactions, Analytics.
result: pass

### 2. Empty state renders when no insights exist
expected: When you navigate to /insights and no insights have been generated yet, you see an empty state with a Sparkles icon, a title, description text, and a "Generate Insights" CTA button — not a blank page or error.
result: pass

### 3. Generate button — loading state
expected: Clicking "Generate New Insights" at the top of the page triggers a loading state. The button shows a spinner and changes text to "Generating..." while the request is in flight.
result: pass

### 4. Generate button — cooldown after generation
expected: After insights are generated, the button becomes disabled and its label changes to something like "Refreshes in 60 minutes" with a countdown. Reloading the page should still show the cooldown (it's stored in localStorage).
result: pass

### 5. 5 category tabs
expected: The insights page shows 5 tabs: Spending Patterns, Recurring Charges, Savings Opportunities, Anomalies, and Comparisons. Clicking each tab switches to show only the insights for that category.
result: pass

### 6. Insight card fields
expected: Each insight card shows: a category icon, a title (summary), narrative text, a key metric pill (e.g., "€ 245/mo"), and optionally a CTA link. The generated timestamp is also shown somewhere on the card or page.
result: issue
reported: "i see all that. but the 'Recurring charges' and 'Saving opportunities' tabs show the same insight 'Recurring expenses account for...'"
severity: major

### 7. Savings Tracker checklist
expected: If subscription insights exist, a "Savings Tracker" card appears. It shows a checklist of recurring subscription insights. Checking an item removes its monthly cost from the running savings total shown in the card.
result: pass

### 8. Dashboard callout links point to /insights
expected: Navigate to /home (the dashboard). The insights callout section has links like "View Insights" and "Generate New Insights". Clicking any of them navigates to /insights — not /stats or any other route.
result: pass

## Summary

total: 8
passed: 7
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Each category tab shows only insights belonging to that category — Recurring Charges and Savings Opportunities tabs show distinct, correctly filtered insights"
  status: failed
  reason: "User reported: 'Recurring charges' and 'Saving opportunities' tabs show the same insight 'Recurring expenses account for...'"
  severity: major
  test: 6
  root_cause: "Both SECTION_CONFIG entries ('recurring_charges' and 'savings_opportunities') use sections: ['subscriptions']. The savings_opportunities filter checks typeof insight.supporting_metrics?.monthly_cost === 'number', but monthly_cost is present on every subscription insight (backend always emits it), so the filter never excludes anything — both tabs return the identical insight list."
  artifacts:
    - path: "web-app/src/lib/insights-helpers.ts"
      issue: "Lines 17-32: savings_opportunities filter predicate matches every subscription insight because monthly_cost is always present"
    - path: "server/app/agents/insights/aggregator.py"
      issue: "Lines 95-108: subscription insight always includes monthly_cost in supporting_metrics, making the filter non-discriminating"
  missing:
    - "Backend needs to emit a distinct section value (e.g. 'savings') for savings-oriented insights, OR frontend filter must discriminate on a field that is only present on a true subset of subscription insights"
  debug_session: ""

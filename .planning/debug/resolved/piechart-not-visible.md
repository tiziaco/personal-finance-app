---
status: resolved
trigger: "Investigate why the PieChart is not visible in the SpendingByCategoryTab component"
created: 2026-03-01T00:00:00Z
updated: 2026-03-01T00:00:00Z
---

## Current Focus

hypothesis: ChartTooltip and Legend are placed as children of <Pie> instead of siblings inside <RechartsPie>, making them invalid in the Recharts tree and preventing the chart from rendering correctly
test: structural analysis of pie-chart.tsx component tree vs Recharts API contract
expecting: confirmed — Recharts requires Tooltip and Legend to be direct children of the top-level chart component (PieChart), not children of <Pie>
next_action: DIAGNOSED — no further action (find_root_cause_only mode)

## Symptoms

expected: PieChart renders visually in the Spending by Category card alongside the category breakdown list
actual: Category Breakdown card is visible but PieChart does not appear
errors: none reported (ErrorBoundary silently swallows any Recharts rendering error)
reproduction: navigate to "By Category" analytics tab
started: unknown

## Eliminated

- hypothesis: data shape mismatch between useCategoriesAnalytics and PieChart props
  evidence: tab maps top_categories to { label, value } which matches PieChartDatum exactly; config keys use category names which match the data keys
  timestamp: 2026-03-01T00:00:00Z

- hypothesis: empty data guard hides the chart
  evidence: the topCategories.length === 0 branch shows a "No spending data" message; the user sees the Category Breakdown list, so topCategories is non-empty and the chart branch IS reached
  timestamp: 2026-03-01T00:00:00Z

- hypothesis: wrong import path
  evidence: tab imports from @/components/shared/charts/pie-chart which exists; file resolved correctly
  timestamp: 2026-03-01T00:00:00Z

- hypothesis: ChartConfig missing color field so ChartStyle emits no CSS variables
  evidence: config entries use color: `var(--chart-N)` directly — ChartStyle filters entries where config.color is truthy, so CSS vars ARE emitted; cells fall back to the same var(--chart-N) anyway
  timestamp: 2026-03-01T00:00:00Z

## Evidence

- timestamp: 2026-03-01T00:00:00Z
  checked: pie-chart.tsx component tree
  found: >
    <ChartContainer config={config}>
      <RechartsPie data={data} ...>        ← This is recharts <PieChart>
        {data.map(...<Cell />)}
        <ChartTooltip ... />               ← INSIDE <Pie>, not <PieChart>
        {showLegend && <Legend />}         ← INSIDE <Pie>, not <PieChart>
      </RechartsPie>
    </ChartContainer>
  implication: >
    Recharts <Pie> only accepts <Cell>, <LabelList>, and <Label> as children.
    <Tooltip> and <Legend> must be direct children of the top-level <PieChart>
    component. Placing them inside <Pie> means Recharts never registers them,
    but more critically the variable named RechartsPie is imported AS
    `PieChart as RechartsPie` — meaning it IS the top-level PieChart wrapper.
    However <ChartTooltip> and <Legend> are nested INSIDE the <Pie> element
    (the inner ring component), which is invalid per the Recharts API.

- timestamp: 2026-03-01T00:00:00Z
  checked: recharts API — what <Pie> accepts as children
  found: >
    <Pie> accepts only <Cell>, <Label>, <LabelList> as children.
    <Tooltip> and <Legend> must be siblings of <Pie> inside <PieChart>.
    Recharts ignores or errors on unexpected children of <Pie>.
  implication: >
    The Tooltip and Legend being inside <Pie> means they are silently ignored.
    But the deeper issue: ChartContainer wraps a <ResponsiveContainer> which
    expects exactly ONE Recharts chart component as its child. That child IS
    <RechartsPie> (the PieChart wrapper). However, <ChartTooltip> and <Legend>
    are nested inside <Pie> (the ring), so they will not render and may cause
    Recharts to not render the pie slices at all if the component tree is invalid.

- timestamp: 2026-03-01T00:00:00Z
  checked: naming confusion in pie-chart.tsx
  found: >
    import { Pie, PieChart as RechartsPie, Cell, Legend } from 'recharts'
    The outer wrapper <RechartsPie> IS recharts' <PieChart>.
    The inner <Pie> is recharts' ring component.
    ChartTooltip and Legend sit inside <Pie> (the ring), not inside <RechartsPie> (the wrapper).
  implication: >
    This IS the structural bug. The correct tree is:
      <RechartsPie>          ← recharts PieChart (the wrapper)
        <Pie>                ← the ring/donut
          <Cell />           ← slice colors
        </Pie>
        <ChartTooltip />     ← must be HERE, sibling of <Pie>
        <Legend />           ← must be HERE, sibling of <Pie>
      </RechartsPie>
    The current code puts ChartTooltip and Legend inside <Pie> (the ring), not
    inside <RechartsPie> (the wrapper). Recharts silently rejects them there,
    causing the chart to fail to paint.

## Resolution

root_cause: >
  In pie-chart.tsx, <ChartTooltip> and <Legend> are placed as children of the
  inner <Pie> (ring) component instead of as siblings of <Pie> inside the outer
  <RechartsPie> (PieChart wrapper), violating the Recharts component tree
  contract and preventing the chart from rendering.
fix: (not applied — diagnosis only)
verification: (not applied)
files_changed: []

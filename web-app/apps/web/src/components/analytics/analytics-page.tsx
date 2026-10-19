"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@app/ui/tabs"

import { CategoryTab } from "./category-tab"
import { FlowTab } from "./flow-tab"
import { SeasonalityTab } from "./seasonality-tab"
import { TrendsTab } from "./trends-tab"
import {
  ANALYTICS_TABS,
  isAnalyticsTab,
  type AnalyticsTab,
  useAnalyticsParams,
} from "./use-analytics-params"

const LABELS: Record<AnalyticsTab, string> = {
  category: "By category",
  flow: "Income vs Expenses",
  trends: "Trends",
  seasonality: "Seasonality",
}

/**
 * The analytics page: four tabs, the open one and each one's period kept in
 * the URL. An inactive tab is not mounted, so its queries run only once opened.
 */
export function AnalyticsPage() {
  const { tab, setTab, months, setMonths } = useAnalyticsParams()

  return (
    <div className="min-w-0 space-y-4">
      <h1 className="text-2xl font-semibold">Analytics</h1>
      <Tabs
        value={tab}
        onValueChange={(v) => {
          if (isAnalyticsTab(v)) setTab(v)
        }}
      >
        <div className="-mx-1 overflow-x-auto px-1 pb-1">
          <TabsList>
            {ANALYTICS_TABS.map((value) => (
              <TabsTrigger key={value} value={value} className="px-2.5">
                {LABELS[value]}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        <TabsContent value="category">
          <CategoryTab
            months={months("category")}
            onMonthsChange={(n) => setMonths("category", n)}
          />
        </TabsContent>
        <TabsContent value="flow">
          <FlowTab
            months={months("flow")}
            onMonthsChange={(n) => setMonths("flow", n)}
          />
        </TabsContent>
        <TabsContent value="trends">
          <TrendsTab
            months={months("trends")}
            onMonthsChange={(n) => setMonths("trends", n)}
          />
        </TabsContent>
        <TabsContent value="seasonality">
          <SeasonalityTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

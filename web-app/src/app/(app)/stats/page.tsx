'use client'

import { useState } from 'react'
import { Tabs } from '@base-ui/react/tabs'
import { SpendingByCategoryTab } from '@/components/analytics/spending-by-category-tab'
import { IncomeVsExpensesTab } from '@/components/analytics/income-vs-expenses-tab'
import { TrendsTab } from '@/components/analytics/trends-tab'
import { SeasonalityTab } from '@/components/analytics/seasonality-tab'
import { ErrorBoundary } from '@/components/shared/error-boundary'
import { cn } from '@/lib/utils'

// Tab definitions — value is used as the key in visitedTabs Set and as the Tabs.Tab value
const TABS = [
  { value: 'category', label: 'By Category' },
  { value: 'income-expenses', label: 'Income vs Expenses' },
  { value: 'trends', label: 'Trends' },
  { value: 'seasonality', label: 'Seasonality' },
] as const

type TabValue = typeof TABS[number]['value']

export default function AnalyticsPage() {
  // activeTab: which tab is currently shown
  // visitedTabs: accumulates all tabs ever activated — gates enabled flags to prevent re-fetch
  const [activeTab, setActiveTab] = useState<TabValue>('category')
  const [visitedTabs, setVisitedTabs] = useState<Set<TabValue>>(new Set(['category']))

  // CRITICAL: onValueChange receives string | number — cast to string, then narrow to TabValue
  // This is a safe cast because all TABS values are strings
  const handleTabChange = (value: string | number) => {
    const tab = String(value) as TabValue
    setActiveTab(tab)
    // Add to visited Set — once added, enabled stays true even when tab is not active
    // This prevents re-fetch on revisit (React Query caches; enabled=true just unlocks the cache lookup)
    setVisitedTabs(prev => new Set([...prev, tab]))
  }

  return (
    <div className="container max-w-6xl mx-auto py-8 space-y-6">
      <h1 className="text-2xl font-bold">Analytics</h1>

      <Tabs.Root value={activeTab} onValueChange={handleTabChange}>
        {/* Tab navigation */}
        <Tabs.List className="flex border-b border-border">
          {TABS.map(tab => (
            <Tabs.Tab
              key={tab.value}
              value={tab.value}
              className={cn(
                'px-4 py-2 text-sm font-medium text-muted-foreground',
                'data-[active]:text-foreground data-[active]:border-b-2 data-[active]:border-primary',
                'focus-visible:outline-none transition-colors cursor-pointer'
              )}
            >
              {tab.label}
            </Tabs.Tab>
          ))}
        </Tabs.List>

        {/* Tab panels — keepMounted defaults to false, panels unmount when not active */}
        <Tabs.Panel value="category" className="pt-6">
          <ErrorBoundary>
            {/* enabled=true immediately (initial tab) */}
            <SpendingByCategoryTab enabled={visitedTabs.has('category')} />
          </ErrorBoundary>
        </Tabs.Panel>

        <Tabs.Panel value="income-expenses" className="pt-6">
          <ErrorBoundary>
            {/* enabled=false until user clicks this tab for the first time */}
            <IncomeVsExpensesTab enabled={visitedTabs.has('income-expenses')} />
          </ErrorBoundary>
        </Tabs.Panel>

        <Tabs.Panel value="trends" className="pt-6">
          <ErrorBoundary>
            {/* enabled=false until user clicks this tab for the first time */}
            <TrendsTab enabled={visitedTabs.has('trends')} />
          </ErrorBoundary>
        </Tabs.Panel>

        <Tabs.Panel value="seasonality" className="pt-6">
          <ErrorBoundary>
            {/* enabled=false until user clicks this tab for the first time */}
            <SeasonalityTab enabled={visitedTabs.has('seasonality')} />
          </ErrorBoundary>
        </Tabs.Panel>
      </Tabs.Root>
    </div>
  )
}

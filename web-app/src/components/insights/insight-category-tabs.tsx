'use client'

import { useState } from 'react'
import { Tabs } from '@base-ui/react/tabs'
import { SECTION_CONFIG, getInsightsForCategory } from '@/lib/insights-helpers'
import { InsightCard } from '@/components/insights/insight-card'
import { cn } from '@/lib/utils'
import type { Insight } from '@/types/insights'

interface InsightCategoryTabsProps {
  insights: Insight[]
  generatedAt: string  // ISO 8601 — passed to each InsightCard
}

export function InsightCategoryTabs({ insights, generatedAt }: InsightCategoryTabsProps) {
  const [activeCategory, setActiveCategory] = useState(SECTION_CONFIG[0].key)

  const handleCategoryChange = (value: string | number) => {
    setActiveCategory(String(value))
  }

  return (
    <Tabs.Root value={activeCategory} onValueChange={handleCategoryChange}>
      <Tabs.List className="flex border-b border-border flex-wrap gap-y-1">
        {SECTION_CONFIG.map(cat => {
          const Icon = cat.icon
          return (
            <Tabs.Tab
              key={cat.key}
              value={cat.key}
              className={cn(
                'flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-muted-foreground',
                'data-[active]:text-foreground data-[active]:border-b-2 data-[active]:border-primary',
                'focus-visible:outline-none transition-colors cursor-pointer'
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {cat.label}
            </Tabs.Tab>
          )
        })}
      </Tabs.List>

      {SECTION_CONFIG.map(cat => {
        const categoryInsights = getInsightsForCategory(insights, cat.key)
        return (
          <Tabs.Panel key={cat.key} value={cat.key} className="pt-6">
            {categoryInsights.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-sm text-muted-foreground">
                  No {cat.label.toLowerCase()} insights found.
                </p>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {categoryInsights.map(insight => (
                  <InsightCard
                    key={insight.insight_id}
                    insight={insight}
                    generatedAt={generatedAt}
                  />
                ))}
              </div>
            )}
          </Tabs.Panel>
        )
      })}
    </Tabs.Root>
  )
}

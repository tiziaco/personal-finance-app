'use client'

import { useState } from 'react'
import type { Insight } from '@/types/insights'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PiggyBank } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SavingsTrackerProps {
  insights: Insight[]
}

export function SavingsTracker({ insights }: SavingsTrackerProps) {
  const savingsInsights = insights.filter(
    i =>
      i.type === 'recurring_subscriptions' &&
      typeof i.supporting_metrics?.monthly_cost === 'number'
  )

  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())

  if (savingsInsights.length === 0) return null

  const toggleChecked = (id: string) => {
    setCheckedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const totalSavings = savingsInsights
    .filter(i => !checkedIds.has(i.insight_id))
    .reduce((sum, i) => sum + (i.supporting_metrics.monthly_cost as number), 0)

  const formattedTotal = new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
  }).format(totalSavings)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <PiggyBank className="h-5 w-5 text-primary" />
          <CardTitle>Savings Tracker</CardTitle>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Potential monthly savings:{' '}
          <span className="font-semibold text-foreground">{formattedTotal}</span>
        </p>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {savingsInsights.map(insight => {
            const cost = insight.supporting_metrics.monthly_cost as number
            const isChecked = checkedIds.has(insight.insight_id)
            return (
              <li key={insight.insight_id} className="flex items-start gap-3">
                <input
                  type="checkbox"
                  id={insight.insight_id}
                  checked={isChecked}
                  onChange={() => toggleChecked(insight.insight_id)}
                  className="mt-0.5 h-4 w-4 cursor-pointer accent-primary"
                />
                <label
                  htmlFor={insight.insight_id}
                  className={cn(
                    'text-sm cursor-pointer flex-1',
                    isChecked && 'line-through text-muted-foreground'
                  )}
                >
                  {insight.summary}
                  <span className="ml-2 font-medium text-primary">
                    {new Intl.NumberFormat('de-DE', {
                      style: 'currency',
                      currency: 'EUR',
                    }).format(cost)}/mo
                  </span>
                </label>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

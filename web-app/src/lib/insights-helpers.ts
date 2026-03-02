import { TrendingUp, RefreshCw, PiggyBank, AlertTriangle, BarChart2 } from 'lucide-react'
import type { Insight, InsightType } from '@/types/insights'

// ---------------------------------------------------------------------------
// Section config — maps 5 display categories to backend section values
// ---------------------------------------------------------------------------

export const SECTION_CONFIG = [
  {
    key: 'spending_patterns',
    label: 'Spending Patterns',
    icon: TrendingUp,
    sections: ['spending', 'behavior'] as string[],
    filter: undefined as ((insight: Insight) => boolean) | undefined,
  },
  {
    key: 'recurring_charges',
    label: 'Recurring Charges',
    icon: RefreshCw,
    sections: ['subscriptions'] as string[],
    filter: undefined as ((insight: Insight) => boolean) | undefined,
  },
  {
    key: 'savings_opportunities',
    label: 'Savings Opportunities',
    icon: PiggyBank,
    sections: ['subscriptions'] as string[],
    // Savings Opportunities = subscription insights that have monthly_cost
    // NOTE: backend has no "savings" section — derived from subscriptions with monthly_cost
    filter: (insight: Insight) =>
      typeof insight.supporting_metrics?.monthly_cost === 'number',
  },
  {
    key: 'anomalies',
    label: 'Anomalies',
    icon: AlertTriangle,
    sections: ['anomalies'] as string[],
    filter: undefined as ((insight: Insight) => boolean) | undefined,
  },
  {
    key: 'comparisons',
    label: 'Comparisons',
    icon: BarChart2,
    sections: ['trends'] as string[],
    filter: undefined as ((insight: Insight) => boolean) | undefined,
  },
]

// ---------------------------------------------------------------------------
// Icon map — type → Lucide icon component
// ---------------------------------------------------------------------------

import { Sparkles, Brain, Store, ShieldCheck } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export const INSIGHT_ICON_MAP: Record<InsightType, LucideIcon> = {
  spending_behavior: Sparkles,
  recurring_subscriptions: RefreshCw,
  trend: TrendingUp,
  behavioral: Brain,
  merchant: Store,
  stability: ShieldCheck,
  anomaly: AlertTriangle,
}

// ---------------------------------------------------------------------------
// Helper: inline currency formatter (formatCurrency not in @/lib/utils)
// ---------------------------------------------------------------------------

function formatCurrencyInline(amount: number): string {
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
  }).format(amount)
}

// ---------------------------------------------------------------------------
// getCategoryForInsight — returns the display category key for an insight
// Falls back to 'spending_patterns' if no match found
// ---------------------------------------------------------------------------

export function getCategoryForInsight(insight: Insight): string {
  for (const config of SECTION_CONFIG) {
    if (config.sections.includes(insight.section)) {
      return config.key
    }
  }
  return 'spending_patterns'
}

// ---------------------------------------------------------------------------
// getInsightsForCategory — filters the full insight list for a display category key
// Applies both section match AND optional filter predicate from SECTION_CONFIG
// ---------------------------------------------------------------------------

export function getInsightsForCategory(
  insights: Insight[],
  categoryKey: string,
): Insight[] {
  const config = SECTION_CONFIG.find((c) => c.key === categoryKey)
  if (!config) return []

  return insights.filter((insight) => {
    const sectionMatch = config.sections.includes(insight.section)
    if (!sectionMatch) return false
    if (config.filter) return config.filter(insight)
    return true
  })
}

// ---------------------------------------------------------------------------
// getKeyMetric — defensively extracts a display string from supporting_metrics
// ---------------------------------------------------------------------------

export function getKeyMetric(insight: Insight): string {
  const m = insight.supporting_metrics

  switch (insight.type) {
    case 'recurring_subscriptions': {
      if (typeof m.monthly_cost === 'number') {
        return `${formatCurrencyInline(m.monthly_cost)}/month`
      }
      break
    }
    case 'spending_behavior': {
      if (typeof m.percentage === 'number') {
        const pct = m.percentage
        const display =
          pct < 1
            ? `${(pct * 100).toFixed(1)}%`
            : `${pct.toFixed(1)}%`
        return display
      }
      break
    }
    case 'anomaly': {
      if (typeof m.anomaly_count === 'number') {
        return `${m.anomaly_count} outliers detected`
      }
      break
    }
    case 'trend': {
      if (typeof m.mom_growth === 'number') {
        const sign = m.mom_growth > 0 ? '+' : ''
        return `${sign}${m.mom_growth.toFixed(1)}% MoM`
      }
      break
    }
    case 'behavioral': {
      if (typeof m.weekend_bias_percentage === 'number') {
        return `${m.weekend_bias_percentage.toFixed(1)}% weekend spending`
      }
      break
    }
  }

  // Fallback: confidence percentage
  return `${Math.round(insight.confidence * 100)}% confidence`
}

// ---------------------------------------------------------------------------
// getCTAForInsight — returns optional CTA link for an insight
// ---------------------------------------------------------------------------

export function getCTAForInsight(
  insight: Insight,
): { label: string; href: string } | null {
  switch (insight.section) {
    case 'subscriptions':
      return {
        label: 'Review Subscriptions',
        href: '/transactions?category=Subscriptions',
      }
    case 'anomalies':
      return { label: 'View Anomalies', href: '/transactions' }
    case 'spending':
    case 'behavior':
      return { label: 'View Transactions', href: '/transactions' }
    default:
      return null
  }
}

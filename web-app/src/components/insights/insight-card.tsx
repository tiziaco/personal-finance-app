import type { Insight, InsightType } from '@/types/insights'
import { getKeyMetric, getCTAForInsight } from '@/lib/insights-helpers'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import Link from 'next/link'
import { buttonVariants } from '@/components/ui/button'
import {
  Sparkles,
  RefreshCw,
  TrendingUp,
  Brain,
  Store,
  ShieldCheck,
  AlertTriangle,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const INSIGHT_ICONS: Record<InsightType, LucideIcon> = {
  spending_behavior: Sparkles,
  recurring_subscriptions: RefreshCw,
  trend: TrendingUp,
  behavioral: Brain,
  merchant: Store,
  stability: ShieldCheck,
  anomaly: AlertTriangle,
}

const SEVERITY_CLASSES: Record<string, string> = {
  critical: 'text-destructive border-destructive/30 bg-destructive/5',
  high: 'text-destructive border-destructive/20 bg-destructive/5',
  medium: 'text-yellow-600 border-yellow-200 bg-yellow-50',
  low: 'text-muted-foreground',
  info: 'text-muted-foreground',
}

interface InsightCardProps {
  insight: Insight
  /** ISO 8601 from InsightsResponse.generated_at, shared across all cards */
  generatedAt: string
}

export function InsightCard({ insight, generatedAt }: InsightCardProps) {
  const Icon = INSIGHT_ICONS[insight.type] ?? Sparkles
  const keyMetric = getKeyMetric(insight)
  const cta = getCTAForInsight(insight)
  const severityClass = SEVERITY_CLASSES[insight.severity] ?? 'text-muted-foreground'

  // Format generated_at for display
  const generatedDate = new Date(generatedAt)
  const formattedDate = generatedDate.toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <Card className={cn('border', severityClass)}>
      <CardHeader className="pb-2">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-full bg-muted shrink-0">
            <Icon className="h-4 w-4 text-foreground" />
          </div>
          <div className="flex-1 min-w-0">
            <CardTitle className="text-base leading-snug">{insight.summary}</CardTitle>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Description — narrative_analysis is the fuller 2-3 sentence text */}
        {insight.narrative_analysis && (
          <p className="text-sm text-muted-foreground">{insight.narrative_analysis}</p>
        )}
        {/* Key metric highlight */}
        {keyMetric && (
          <div className="inline-flex items-center px-3 py-1 rounded-full bg-muted text-sm font-medium">
            {keyMetric}
          </div>
        )}
        {/* Optional CTA */}
        {cta && (
          <Link
            href={cta.href}
            className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
          >
            {cta.label}
          </Link>
        )}
        {/* Timestamp — generated_at is on the InsightsResponse envelope, not per-card */}
        <p className="text-xs text-muted-foreground">Generated {formattedDate}</p>
      </CardContent>
    </Card>
  )
}

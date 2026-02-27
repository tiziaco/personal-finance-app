export type InsightType =
  | 'spending_behavior'
  | 'recurring_subscriptions'
  | 'trend'
  | 'behavioral'
  | 'merchant'
  | 'stability'
  | 'anomaly'

export type SeverityLevel = 'info' | 'low' | 'medium' | 'high' | 'critical'

export interface Insight {
  insight_id: string
  type: InsightType
  severity: SeverityLevel
  time_window: string
  summary: string
  narrative_analysis: string | null
  supporting_metrics: Record<string, unknown>
  confidence: number
  section: string
}

export interface InsightsResponse {
  insights: Insight[]
  /** ISO 8601 datetime string */
  generated_at: string
}

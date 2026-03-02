import { Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface InsightsEmptyStateProps {
  onGenerate: () => void
  isGenerating: boolean
}

export function InsightsEmptyState({ onGenerate, isGenerating }: InsightsEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-6 text-center">
      <Sparkles className="h-16 w-16 text-muted-foreground/40" />
      <div className="space-y-2">
        <h3 className="text-lg font-semibold text-foreground">No insights yet</h3>
        <p className="text-sm text-muted-foreground max-w-sm">
          Generate AI-powered insights to understand your spending patterns, subscriptions, and savings opportunities.
        </p>
      </div>
      <Button onClick={onGenerate} disabled={isGenerating} size="lg">
        {isGenerating ? 'Generating...' : 'Generate Insights'}
      </Button>
    </div>
  )
}

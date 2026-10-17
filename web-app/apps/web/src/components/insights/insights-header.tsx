import { Button } from "@app/ui/button"
import { generatedLabel } from "./labels"

export function InsightsHeader({
  generatedAt,
  pending,
  error,
  onRegenerate,
}: {
  generatedAt?: string | null
  pending: boolean
  error: boolean
  /** Omitted when there is nothing to regenerate (no data yet). */
  onRegenerate?: () => void
}) {
  const generated = generatedLabel(generatedAt)
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Insights</h1>
        <p className="text-sm text-muted-foreground">
          What stands out in your spending, written from your own figures.
        </p>
      </div>
      {onRegenerate && (
        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-3">
            {generated && (
              <span className="text-sm text-muted-foreground">{generated}</span>
            )}
            <Button
              variant="outline"
              size="sm"
              disabled={pending}
              onClick={onRegenerate}
            >
              {pending ? "Generating…" : "Regenerate"}
            </Button>
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              Couldn&apos;t regenerate insights.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

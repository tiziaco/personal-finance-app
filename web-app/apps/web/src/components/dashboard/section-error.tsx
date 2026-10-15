import { Button } from "@app/ui/button"
import { Card, CardContent } from "@app/ui/card"

/** A section that failed on its own: say so, offer a retry, leave the rest of the page alone. */
export function SectionError({
  what,
  onRetry,
}: {
  what: string
  onRetry: () => void
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">
          Couldn&apos;t load {what}.
        </p>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </CardContent>
    </Card>
  )
}

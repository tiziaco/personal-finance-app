import { Skeleton } from "@app/ui/skeleton"
import { CardsSkeleton } from "@/components/insights/cards-skeleton"

export default function InsightsLoading() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-48" />
      <CardsSkeleton />
    </div>
  )
}

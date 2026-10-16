import { Skeleton } from "@app/ui/skeleton"

export default function AnalyticsLoading() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-96 w-full" />
    </div>
  )
}

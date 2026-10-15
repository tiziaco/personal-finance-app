import { Skeleton } from "@app/ui/skeleton"
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton"

export default function HomeLoading() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-64" />
      <DashboardSkeleton />
    </div>
  )
}

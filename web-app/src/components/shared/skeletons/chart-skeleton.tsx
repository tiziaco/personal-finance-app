import { Skeleton } from '@/components/ui/skeleton'

interface ChartSkeletonProps {
  className?: string
  variant?: 'bar' | 'pie' | 'line'  // default 'bar'; adjusts visual shape
}

export function ChartSkeleton({ className, variant = 'bar' }: ChartSkeletonProps) {
  if (variant === 'pie') {
    return (
      <div className={`flex items-center justify-center ${className}`}>
        <Skeleton className="h-48 w-48 rounded-full" />
      </div>
    )
  }

  // bar and line share the same bar-chart skeleton appearance
  return (
    <div className={`flex items-end gap-2 h-48 ${className}`}>
      {[40, 70, 55, 90, 65, 80, 45].map((h, i) => (
        <Skeleton
          key={i}
          style={{ height: `${h}%` }}
          className="flex-1 rounded-t"
        />
      ))}
    </div>
  )
}

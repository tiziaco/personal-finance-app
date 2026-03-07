import { Skeleton } from '@/components/ui/skeleton'

interface TableSkeletonProps {
  rows?: number     // default 10; use 25 for full transaction table page
  columns?: number  // default 7; matches transaction table column count
}

export function TableSkeleton({ rows = 10, columns = 7 }: TableSkeletonProps) {
  return (
    <div className="w-full space-y-2">
      {/* Header row */}
      <div className="flex gap-4 pb-2 border-b">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Data rows */}
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div key={rowIdx} className="flex gap-4 py-2">
          {Array.from({ length: columns }).map((_, colIdx) => (
            <Skeleton key={colIdx} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

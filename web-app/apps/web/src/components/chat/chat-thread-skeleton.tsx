import { Skeleton } from "@app/ui/skeleton"

/** The thread pane while a conversation's history loads. */
export function ChatThreadSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 pt-4">
      <Skeleton className="ml-auto h-10 w-1/2 rounded-2xl" />
      <Skeleton className="h-24 w-3/4" />
      <Skeleton className="ml-auto h-10 w-1/3 rounded-2xl" />
    </div>
  )
}

import { PiggyBank } from "lucide-react"

export default function BudgetsPage() {
  return (
    <main className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center px-4">
      <PiggyBank className="w-16 h-16 text-muted-foreground" />
      <h1 className="text-3xl font-semibold">Coming Soon</h1>
      <p className="text-muted-foreground max-w-sm">
        Budget tracking is on its way. Set spending limits by category,
        track your progress month by month, and get alerts when you&apos;re
        approaching your limit.
      </p>
    </main>
  )
}

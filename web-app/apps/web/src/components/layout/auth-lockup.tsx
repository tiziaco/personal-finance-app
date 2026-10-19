import type { ReactNode } from "react"
import { FinsightMark } from "@app/components/layout/finsight-mark"

/** The sign-in and sign-up column: the Finsight lockup above Clerk's card. */
export function AuthLockup({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
      <div className="flex items-center gap-3">
        <FinsightMark className="w-14" />
        <span className="text-h1 tracking-tight">Finsight</span>
      </div>
      {children}
    </div>
  )
}

"use client"

import { useAppAuth } from "@app/auth"
import { formatMonth } from "./month"

export function WelcomeHeader({
  referenceMonth,
}: {
  referenceMonth?: string | null
}) {
  const { user } = useAppAuth()
  const firstName = user?.name?.trim().split(/\s+/)[0]
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold tracking-tight">
        {firstName ? `Welcome back, ${firstName}` : "Welcome back"}
      </h1>
      <p className="text-sm text-muted-foreground">
        {referenceMonth
          ? `Your overview for ${formatMonth(referenceMonth)}`
          : "Your overview"}
      </p>
    </div>
  )
}

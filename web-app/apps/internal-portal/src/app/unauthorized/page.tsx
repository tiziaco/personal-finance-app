"use client"

import { useAppAuth } from "@app/auth"
import { Button } from "@app/ui/button"

export default function UnauthorizedPage() {
  const { signOut } = useAppAuth()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-2xl font-semibold">Access denied</h1>
      <p className="text-muted-foreground max-w-md">
        Your account does not have access to the internal portal. Contact an
        administrator if you think this is a mistake.
      </p>
      <Button onClick={() => void signOut()}>Sign out</Button>
    </div>
  )
}

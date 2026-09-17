"use client"

import { useClerk } from "@clerk/nextjs"
import { Button } from "@app/ui/button"

export default function UnauthorizedPage() {
  const { signOut } = useClerk()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-2xl font-semibold">Accesso non consentito</h1>
      <p className="text-muted-foreground max-w-md">
        Il tuo account non ha i permessi per accedere al portale fornitori.
        Contatta un amministratore se ritieni che si tratti di un errore.
      </p>
      <Button onClick={() => signOut({ redirectUrl: "/sign-in" })}>Esci</Button>
    </div>
  )
}

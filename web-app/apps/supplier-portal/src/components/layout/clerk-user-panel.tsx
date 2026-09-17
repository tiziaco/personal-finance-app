"use client"

import { useClerk } from "@clerk/nextjs"
import { useAppAuth, Role } from "@app/auth"
import { UserDetailsPanel } from "@app/ui/layout/user-panel"

export function ClerkUserPanel() {
  const { isLoaded, user, role } = useAppAuth()
  const { signOut, openUserProfile, openOrganizationProfile } = useClerk()

  return (
    <UserDetailsPanel
      user={
        isLoaded && user
          ? {
              name:
                [user.firstName, user.lastName].filter(Boolean).join(" ") ||
                "User",
              email: user.primaryEmailAddress?.emailAddress ?? "No email",
              imageUrl: user.imageUrl,
            }
          : null
      }
      // Sign out straight to /sign-in. The default lands on `/`, which
      // middleware then bounces twice to reach the same place.
      onSignOut={() => signOut({ redirectUrl: "/sign-in" })}
      onOpenProfile={() => openUserProfile()}
      onOpenOrganizationProfile={
        role === Role.PROJECT_MANAGER
          ? () => openOrganizationProfile()
          : undefined
      }
    />
  )
}

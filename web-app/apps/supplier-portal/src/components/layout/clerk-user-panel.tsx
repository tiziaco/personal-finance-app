"use client"

import { useClerk } from "@clerk/nextjs"
import { useAppAuth, Role } from "@rilevio/auth"
import { UserDetailsPanel } from "@rilevio/ui/layout/user-panel"

export function ClerkUserPanel() {
  const { isLoaded, user, role } = useAppAuth()
  const { signOut, openUserProfile, openOrganizationProfile } = useClerk()

  return (
    <UserDetailsPanel
      user={isLoaded && user ? {
        name: [user.firstName, user.lastName].filter(Boolean).join(" ") || "User",
        email: user.primaryEmailAddress?.emailAddress ?? "No email",
        imageUrl: user.imageUrl,
      } : null}
      onSignOut={() => signOut()}
      onOpenProfile={() => openUserProfile()}
      onOpenOrganizationProfile={role === Role.PROJECT_MANAGER ? () => openOrganizationProfile() : undefined}
    />
  )
}

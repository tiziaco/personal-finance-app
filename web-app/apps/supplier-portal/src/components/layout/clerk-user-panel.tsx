"use client"

import { useClerk } from "@clerk/nextjs"
import { useAppAuth, Role } from "@app/auth"
import { UserDetailsPanel } from "@app/components/layout/user-panel"

export function ClerkUserPanel() {
  const { isLoaded, user, role, signOut } = useAppAuth()
  const { openUserProfile, openOrganizationProfile } = useClerk()

  return (
    <UserDetailsPanel
      user={
        isLoaded && user
          ? {
              name: user.name ?? "User",
              email: user.email ?? "No email",
              imageUrl: user.imageUrl ?? undefined,
            }
          : null
      }
      onSignOut={() => void signOut()}
      onOpenProfile={() => openUserProfile()}
      onOpenOrganizationProfile={
        role === Role.PROJECT_MANAGER
          ? () => openOrganizationProfile()
          : undefined
      }
    />
  )
}

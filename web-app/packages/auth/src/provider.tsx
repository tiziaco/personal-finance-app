/**
 * AuthProvider and useAppAuth hook.
 *
 * Portability seam: AuthProvider wraps Clerk's hooks to derive identity.
 * When migrating to WorkOS, only AuthProvider's internals change.
 * All components call useAppAuth() — they never call useAuth() or useUser()
 * directly — and the context exposes no vendor type.
 */
"use client"

import { createContext, useCallback, useContext, useMemo } from "react"
import { useAuth, useUser } from "@clerk/nextjs"

/** The signed-in user's profile, as the vendor reports it. */
export interface AppUser {
  /** Full name, or null when the profile has none. */
  name: string | null
  email: string | null
  imageUrl: string | null
}

interface AuthContextValue {
  /** The signed-in user, or null while loading or signed out. */
  user: AppUser | null
  /** True once Clerk has finished initialising the session. */
  isLoaded: boolean
  /**
   * A fresh JWT for the current session, or null when signed out. The only
   * sanctioned way to reach a bearer token: @app/api-client's mutator consumes
   * it, which is what keeps that package off Clerk and on this seam.
   */
  getToken: () => Promise<string | null>
  /**
   * End the session, then load `signOutUrl` as a new document. A router push
   * would keep the heap — every cache and context the previous user filled —
   * alive across a trust boundary.
   */
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoaded: false,
  getToken: async () => null,
  signOut: async () => {},
})

/**
 * Wrap inside ClerkProvider in each app's root layout. `signOutUrl` is the
 * app's route, hence a prop.
 */
export function AuthProvider({
  children,
  signOutUrl = "/",
}: {
  children: React.ReactNode
  signOutUrl?: string
}) {
  const { isLoaded, getToken, signOut: endSession } = useAuth()
  const { user: clerkUser } = useUser()

  const user = useMemo<AppUser | null>(
    () =>
      clerkUser
        ? {
            name:
              [clerkUser.firstName, clerkUser.lastName]
                .filter(Boolean)
                .join(" ") || null,
            email: clerkUser.primaryEmailAddress?.emailAddress ?? null,
            imageUrl: clerkUser.imageUrl || null,
          }
        : null,
    [clerkUser],
  )

  const signOut = useCallback(async () => {
    // Await: navigating away mid-request could leave the session alive.
    // redirectUrl because Clerk navigates too, and its default is "/".
    // finally: if the session is already gone, the destroy rejects, and
    // stranding the user on a signed-in page is the worse failure.
    try {
      await endSession({ redirectUrl: signOutUrl })
    } finally {
      window.location.assign(signOutUrl)
    }
  }, [endSession, signOutUrl])

  return (
    <AuthContext.Provider value={{ user, isLoaded, getToken, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Hook for the current user's identity.
 *
 * Never call useAuth() or useUser() directly in a component, and check
 * isLoaded before rendering user-dependent UI.
 */
export function useAppAuth(): AuthContextValue {
  return useContext(AuthContext)
}

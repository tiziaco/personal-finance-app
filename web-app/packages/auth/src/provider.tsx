/**
 * AuthProvider and useAppAuth hook.
 *
 * Portability seam: AuthProvider wraps Clerk's hooks to derive identity.
 * When migrating to WorkOS, only AuthProvider's internals change.
 * All components call useAppAuth() — they never call useAuth() or useUser()
 * directly — and the context exposes no vendor type.
 */
"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from "react"
import { useAuth, useUser } from "@clerk/nextjs"

/** How long getToken waits for a session being activated before answering null. */
export const SESSION_WAIT_MS = 5000

/** The signed-in user's profile, as the vendor reports it. */
export interface AppUser {
  /** Full name, or null when the profile has none. */
  name: string | null
  email: string | null
  imageUrl: string | null
}

export interface GetTokenOptions {
  /** Skip the cached token and fetch a new one: the server refused the last. */
  forceRefresh?: boolean
}

interface AuthContextValue {
  /** The signed-in user, or null while loading or signed out. */
  user: AppUser | null
  /** True once Clerk has finished initialising the session. */
  isLoaded: boolean
  /** True once Clerk has an active session. Straight after sign-in it trails the navigation. */
  isSignedIn: boolean
  /**
   * A fresh JWT for the current session; null only once the state has settled
   * with no session. Straight after sign-in Clerk reports no session for a moment
   * while it installs the new one, and a null then would send the request bare,
   * so a null from Clerk without a session waits for one, up to SESSION_WAIT_MS.
   * The only sanctioned way to reach a bearer token: @app/api-client's mutator
   * consumes it, which is what keeps that package off Clerk and on this seam.
   */
  getToken: (options?: GetTokenOptions) => Promise<string | null>
  /**
   * End the session, then load `signOutUrl` as a new document. A router push
   * would keep the heap — every cache and context the previous user filled —
   * alive across a trust boundary. A call while one is in flight returns the
   * same promise, so many refused requests sign out once.
   */
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoaded: false,
  isSignedIn: false,
  getToken: async () => null,
  signOut: async () => {},
})

/** True when `waiters` is woken by a session, false after SESSION_WAIT_MS. */
function sessionArrives(waiters: Set<() => void>): Promise<boolean> {
  return new Promise((resolve) => {
    const wake = () => {
      clearTimeout(timer)
      resolve(true)
    }
    const timer = setTimeout(() => {
      waiters.delete(wake)
      resolve(false)
    }, SESSION_WAIT_MS)
    waiters.add(wake)
  })
}

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
  const {
    isLoaded,
    isSignedIn = false,
    getToken: clerkGetToken,
    signOut: endSession,
  } = useAuth()
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

  // getToken outlives the render that made it, so it reads the session through
  // a ref, and the requests waiting for one are woken when it arrives.
  const signedIn = useRef(isSignedIn)
  const waiters = useRef(new Set<() => void>())
  useEffect(() => {
    signedIn.current = isSignedIn
    if (!isSignedIn) return
    for (const wake of waiters.current) wake()
    waiters.current.clear()
  }, [isSignedIn])

  const getToken = useCallback(
    async ({ forceRefresh = false }: GetTokenOptions = {}) => {
      const ask = () =>
        clerkGetToken(forceRefresh ? { skipCache: true } : undefined)
      const token = await ask()
      if (token) return token
      if (!signedIn.current && !(await sessionArrives(waiters.current)))
        return null
      return ask()
    },
    [clerkGetToken],
  )

  // Never cleared: the document load at the end of a sign-out replaces this page.
  const signingOut = useRef<Promise<void> | null>(null)
  const signOut = useCallback(() => {
    // Await: navigating away mid-request could leave the session alive.
    // redirectUrl because Clerk navigates too, and its default is "/".
    // finally: if the session is already gone, the destroy rejects, and
    // stranding the user on a signed-in page is the worse failure.
    signingOut.current ??= (async () => {
      try {
        await endSession({ redirectUrl: signOutUrl })
      } finally {
        window.location.assign(signOutUrl)
      }
    })()
    return signingOut.current
  }, [endSession, signOutUrl])

  return (
    <AuthContext.Provider
      value={{ user, isLoaded, isSignedIn, getToken, signOut }}
    >
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

/**
 * AuthProvider and useAppAuth hook.
 *
 * Portability seam: AuthProvider wraps Clerk's hooks to derive identity and role.
 * When migrating to WorkOS, only AuthProvider's internals change.
 * All components call useAppAuth() — they never call useAuth() or useUser() directly.
 */
"use client"

import { createContext, useContext } from "react"
import { useAuth, useUser } from "@clerk/nextjs"
import type { UserResource } from "@clerk/types"
import { getUserRole, Role } from "./permissions"

interface AuthContextValue {
  /** The Clerk user object, or null/undefined while loading. */
  user: UserResource | null | undefined
  /** The current user's org role, or null if no active org context. */
  role: Role | null
  /** True once Clerk has finished initialising the session. */
  isLoaded: boolean
  /**
   * Returns a fresh JWT for the current session, or null when signed out.
   *
   * This is the only sanctioned way to reach a bearer token. @app/api-client's
   * mutator consumes it, which is what keeps that package dependent on this
   * seam rather than on Clerk.
   */
  getToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  role: null,
  isLoaded: false,
  getToken: async () => null,
})

/**
 * Wrap inside ClerkProvider in each app's root layout.
 *
 * @example
 * // app/layout.tsx
 * <ClerkProvider>
 *   <AuthProvider>
 *     {children}
 *   </AuthProvider>
 * </ClerkProvider>
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isLoaded, orgRole, getToken } = useAuth()
  const { user } = useUser()
  const role = getUserRole(orgRole)

  return (
    <AuthContext.Provider value={{ user, role, isLoaded, getToken }}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Hook for accessing the current user's identity and role.
 *
 * Also the single source of the Clerk session token: `getToken` is exposed
 * here so @app/api-client's mutator can authenticate requests without
 * importing from @clerk/nextjs itself.
 *
 * Rules:
 * - Never call useAuth() or useUser() directly in components.
 * - Always check isLoaded before rendering role-dependent UI.
 *
 * @example
 * const { user, role, isLoaded, getToken } = useAppAuth()
 * if (!isLoaded) return <Skeleton />
 * if (role === Role.PROJECT_MANAGER) { ... }
 *
 * const token = await getToken()   // rarely needed directly — the generated
 *                                  // client already attaches it
 */
export function useAppAuth(): AuthContextValue {
  return useContext(AuthContext)
}

/**
 * Role definitions and utilities for Rilevio RBAC.
 *
 * Portability seam: getUserRole() is the only function that knows how
 * the auth provider represents roles. When migrating to WorkOS, only
 * this function changes — all consumers remain unchanged.
 */

/** Clerk org role slugs with the 'org:' prefix stripped. */
export const Role = {
  PROJECT_MANAGER: "project_manager",
  REVIEWER: "reviewer",
  APPROVER: "approver",
  SUPPLIER: "supplier",
} as const

export type Role = (typeof Role)[keyof typeof Role]

/**
 * Convert a Clerk orgRole string to a Role value.
 *
 * Strips the 'org:' prefix that Clerk adds to all org role slugs.
 * Returns null if orgRole is absent (user has no active org context).
 *
 * @example
 * getUserRole("org:project_manager") // → "project_manager"
 * getUserRole(null)                  // → null
 */
export function getUserRole(orgRole: string | null | undefined): Role | null {
  if (!orgRole) return null
  const stripped = orgRole.replace("org:", "")
  const values = Object.values(Role) as string[]
  if (!values.includes(stripped)) return null
  return stripped as Role
}

/** Returns true for any role that grants access to the internal portal. */
export function isInternalRole(role: Role | null): boolean {
  return role !== null && role !== Role.SUPPLIER
}

/** Returns true only for roles that grant access to the supplier portal. */
export function isSupplierRole(role: Role | null): boolean {
  return role !== null && role === Role.SUPPLIER
}

/** Italian display labels — mapped in the frontend only. */
export const ROLE_LABELS: Record<Role, string> = {
  [Role.PROJECT_MANAGER]: "Project Manager",
  [Role.REVIEWER]: "Revisore",
  [Role.APPROVER]: "Approvatore",
  [Role.SUPPLIER]: "Fornitore",
}

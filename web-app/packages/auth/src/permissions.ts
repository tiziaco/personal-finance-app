/**
 * Role definitions and utilities for RBAC.
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

const ORG_PREFIX = "org:"

/**
 * Convert a Clerk orgRole string to a Role value.
 *
 * Clerk prefixes every org role slug with 'org:'. Only a leading prefix is
 * stripped; a value without one, or naming no known role, is not a role.
 * Returns null when orgRole is absent (no active org context).
 *
 * @example
 * getUserRole("org:project_manager") // → "project_manager"
 * getUserRole("project_manager")     // → null
 * getUserRole(null)                  // → null
 */
export function getUserRole(orgRole: string | null | undefined): Role | null {
  if (!orgRole?.startsWith(ORG_PREFIX)) return null
  const slug = orgRole.slice(ORG_PREFIX.length)
  const values = Object.values(Role) as string[]
  return values.includes(slug) ? (slug as Role) : null
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

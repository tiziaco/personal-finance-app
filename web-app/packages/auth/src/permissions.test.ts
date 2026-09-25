import { describe, expect, it } from "vitest"

import {
  ROLE_LABELS,
  Role,
  getUserRole,
  isInternalRole,
  isSupplierRole,
} from "./permissions"

// getUserRole is the portability seam: the only function that knows how the
// auth provider spells a role. These cases are what a migration must keep.
describe("getUserRole", () => {
  it.each([
    ["org:project_manager", Role.PROJECT_MANAGER],
    ["org:reviewer", Role.REVIEWER],
    ["org:approver", Role.APPROVER],
    ["org:supplier", Role.SUPPLIER],
  ])("narrows %s", (claim, role) => {
    expect(getUserRole(claim)).toBe(role)
  })

  it.each([
    ["an unknown role", "org:admin"],
    ["a role without the prefix", "supplier"],
    ["a prefix that is not leading", "supplierorg:"],
    ["a doubled prefix", "org:org:supplier"],
    ["the wrong case", "org:Supplier"],
    ["the bare prefix", "org:"],
  ])("returns null for %s", (_, claim) => {
    expect(getUserRole(claim)).toBeNull()
  })

  it.each([null, undefined, ""])("returns null for %j", (claim) => {
    expect(getUserRole(claim)).toBeNull()
  })
})

describe("isInternalRole / isSupplierRole", () => {
  it.each([
    [Role.PROJECT_MANAGER, true, false],
    [Role.REVIEWER, true, false],
    [Role.APPROVER, true, false],
    [Role.SUPPLIER, false, true],
    [null, false, false],
  ] as const)("%s → internal %s, supplier %s", (role, internal, supplier) => {
    expect(isInternalRole(role)).toBe(internal)
    expect(isSupplierRole(role)).toBe(supplier)
  })
})

describe("ROLE_LABELS", () => {
  it("labels every role", () => {
    for (const role of Object.values(Role)) {
      expect(ROLE_LABELS[role]).toBeTruthy()
    }
  })
})

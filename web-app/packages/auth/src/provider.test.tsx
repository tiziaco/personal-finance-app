import type { ReactNode } from "react"
import { renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AuthProvider, useAppAuth } from "./provider"

// Only Clerk's hooks are mocked: the mapping from them to the seam's
// vendor-free context is what is under test.
const clerk = vi.hoisted(() => ({
  user: null as Record<string, unknown> | null,
  endSession: vi.fn(),
}))

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    getToken: async () => "jwt",
    signOut: clerk.endSession,
  }),
  useUser: () => ({ user: clerk.user }),
}))

const ada = {
  firstName: "Ada",
  lastName: "Lovelace",
  primaryEmailAddress: { emailAddress: "ada@test.dev" },
  imageUrl: "https://img.test/ada.png",
}

function renderAuth(signOutUrl?: string) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <AuthProvider signOutUrl={signOutUrl}>{children}</AuthProvider>
  }
  return renderHook(() => useAppAuth(), { wrapper: Wrapper }).result
}

// jsdom never navigates; swap location so assign() is observable.
const assign = vi.fn()
const realLocation = window.location

beforeEach(() => {
  clerk.user = null
  clerk.endSession.mockReset()
  assign.mockReset()
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...realLocation, assign },
  })
})

afterEach(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: realLocation,
  })
})

describe("user", () => {
  it("exposes no role", () => {
    expect(renderAuth().current).not.toHaveProperty("role")
  })

  it("is AppUser: these three fields and no vendor field", () => {
    clerk.user = ada
    expect(renderAuth().current.user).toEqual({
      name: "Ada Lovelace",
      email: "ada@test.dev",
      imageUrl: "https://img.test/ada.png",
    })
  })

  it.each([
    [{ firstName: "Ada", lastName: null }, "Ada"],
    [{ firstName: null, lastName: "Lovelace" }, "Lovelace"],
    [{ firstName: null, lastName: null }, null],
    [{ firstName: "", lastName: "" }, null],
  ])("builds the name from %j as %j", (parts, name) => {
    clerk.user = { ...ada, ...parts }
    expect(renderAuth().current.user?.name).toBe(name)
  })

  it("has a null email without a primary address", () => {
    clerk.user = { ...ada, primaryEmailAddress: null }
    expect(renderAuth().current.user?.email).toBeNull()
  })

  it("has a null imageUrl when Clerk's is empty", () => {
    clerk.user = { ...ada, imageUrl: "" }
    expect(renderAuth().current.user?.imageUrl).toBeNull()
  })

  it("is null without a Clerk user", () => {
    expect(renderAuth().current.user).toBeNull()
  })
})

describe("signOut", () => {
  it("navigates only once the session has ended", async () => {
    let endSession!: () => void
    clerk.endSession.mockReturnValue(
      new Promise<void>((resolve) => {
        endSession = resolve
      }),
    )
    const auth = renderAuth("/sign-in")

    const done = auth.current.signOut()
    expect(clerk.endSession).toHaveBeenCalledWith({ redirectUrl: "/sign-in" })
    expect(assign).not.toHaveBeenCalled()

    endSession()
    await done
    expect(assign).toHaveBeenCalledWith("/sign-in")
  })

  it("navigates even when ending the session fails, and still rejects", async () => {
    clerk.endSession.mockRejectedValue(new Error("session already gone"))
    const auth = renderAuth("/sign-in")

    await expect(auth.current.signOut()).rejects.toThrow("session already gone")
    expect(assign).toHaveBeenCalledWith("/sign-in")
  })

  it("defaults to / without a signOutUrl", async () => {
    clerk.endSession.mockResolvedValue(undefined)
    const auth = renderAuth()

    await auth.current.signOut()
    expect(clerk.endSession).toHaveBeenCalledWith({ redirectUrl: "/" })
    expect(assign).toHaveBeenCalledWith("/")
  })
})

import type { ReactNode } from "react"
import { renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AuthProvider, SESSION_WAIT_MS, useAppAuth } from "./provider"

// Only Clerk's hooks are mocked: the mapping from them to the seam's
// vendor-free context is what is under test.
const clerk = vi.hoisted(() => ({
  user: null as Record<string, unknown> | null,
  endSession: vi.fn(),
  isSignedIn: true as boolean | undefined,
  getToken: vi.fn(),
}))

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: clerk.isSignedIn,
    getToken: clerk.getToken,
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

function renderAuthHook(signOutUrl?: string) {
  function Wrapper({ children }: { children: ReactNode }) {
    return <AuthProvider signOutUrl={signOutUrl}>{children}</AuthProvider>
  }
  return renderHook(() => useAppAuth(), { wrapper: Wrapper })
}

function renderAuth(signOutUrl?: string) {
  return renderAuthHook(signOutUrl).result
}

/** Let pending promise callbacks run. */
const flush = () => new Promise((resolve) => setTimeout(resolve, 0))

// jsdom never navigates; swap location so assign() is observable.
const assign = vi.fn()
const realLocation = window.location

beforeEach(() => {
  clerk.user = null
  clerk.endSession.mockReset()
  clerk.isSignedIn = true
  clerk.getToken.mockReset()
  clerk.getToken.mockResolvedValue("jwt")
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

  // Many requests refused at once each ask to sign out; the session ends once.
  it("ends the session once when called again while in flight", async () => {
    clerk.endSession.mockResolvedValue(undefined)
    const auth = renderAuth("/sign-in")

    await Promise.all([auth.current.signOut(), auth.current.signOut()])
    expect(clerk.endSession).toHaveBeenCalledOnce()
    expect(assign).toHaveBeenCalledOnce()
  })
})

describe("getToken", () => {
  it("returns Clerk's token without waiting", async () => {
    await expect(renderAuth().current.getToken()).resolves.toBe("jwt")
    expect(clerk.getToken).toHaveBeenCalledWith(undefined)
  })

  // A hard reload: Clerk has not loaded, so no session yet, but its getToken waits
  // for the load and returns the token. That must come back at once, not after a wait.
  it("returns a token Clerk gives before the session is reported", async () => {
    clerk.isSignedIn = undefined
    await expect(renderAuth().current.getToken()).resolves.toBe("jwt")
    expect(clerk.getToken).toHaveBeenCalledOnce()
  })

  it("asks Clerk for a fresh token on forceRefresh", async () => {
    await renderAuth().current.getToken({ forceRefresh: true })
    expect(clerk.getToken).toHaveBeenCalledWith({ skipCache: true })
  })

  // The first call already waited; a forced refresh only follows a refusal.
  it("does not wait for a session on forceRefresh", async () => {
    clerk.isSignedIn = false
    clerk.getToken.mockResolvedValue(null)

    await expect(
      renderAuth().current.getToken({ forceRefresh: true }),
    ).resolves.toBeNull()
    expect(clerk.getToken).toHaveBeenCalledOnce()
    expect(clerk.getToken).toHaveBeenCalledWith({ skipCache: true })
  })

  // Straight after sign-in: Clerk is loaded but has not installed the session yet.
  it("waits for a session being activated, then returns its token", async () => {
    clerk.isSignedIn = false
    clerk.getToken.mockResolvedValueOnce(null)
    const { result, rerender } = renderAuthHook()

    let token: string | null | undefined
    const pending = result.current.getToken().then((t) => (token = t))
    await flush()
    expect(token).toBeUndefined()

    clerk.isSignedIn = true
    clerk.getToken.mockResolvedValue("fresh")
    rerender()
    await pending
    expect(token).toBe("fresh")
  })

  it("wakes every request waiting for the session", async () => {
    clerk.isSignedIn = false
    clerk.getToken.mockResolvedValue(null)
    const { result, rerender } = renderAuthHook()

    const pending = Promise.all([
      result.current.getToken(),
      result.current.getToken(),
    ])
    await flush()

    clerk.isSignedIn = true
    clerk.getToken.mockResolvedValue("fresh")
    rerender()
    await expect(pending).resolves.toEqual(["fresh", "fresh"])
  })

  it("answers null when no session arrives in time", async () => {
    vi.useFakeTimers()
    try {
      clerk.isSignedIn = false
      clerk.getToken.mockResolvedValue(null)
      const pending = renderAuth().current.getToken()

      await vi.advanceTimersByTimeAsync(SESSION_WAIT_MS)
      await expect(pending).resolves.toBeNull()
      expect(clerk.getToken).toHaveBeenCalledOnce()
    } finally {
      vi.useRealTimers()
    }
  })

  // Signed out from another tab, then signed in again without a document load.
  it("waits again once the session has ended", async () => {
    const { result, rerender } = renderAuthHook()
    clerk.isSignedIn = false
    rerender()
    clerk.getToken.mockResolvedValue(null)

    let token: string | null | undefined
    const pending = result.current.getToken().then((t) => (token = t))
    await flush()
    expect(token).toBeUndefined()

    clerk.isSignedIn = true
    clerk.getToken.mockResolvedValue("again")
    rerender()
    await pending
    expect(token).toBe("again")
  })

  it("exposes no session flag: getToken is the only way to the session", () => {
    expect(renderAuth().current).not.toHaveProperty("isSignedIn")
  })
})

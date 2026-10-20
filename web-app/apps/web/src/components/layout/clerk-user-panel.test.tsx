import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SidebarProvider } from "@app/ui/sidebar"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { ClerkUserPanel } from "./clerk-user-panel"

const mocks = vi.hoisted(() => ({
  auth: {} as Record<string, unknown>,
  signOut: vi.fn(),
  clerk: {
    openUserProfile: vi.fn(),
    signOut: vi.fn(),
  },
}))

vi.mock("@app/auth", () => ({ useAppAuth: () => mocks.auth }))

vi.mock("@clerk/nextjs", () => ({ useClerk: () => mocks.clerk }))

function setAuth(overrides: Record<string, unknown> = {}) {
  mocks.auth = {
    isLoaded: true,
    user: { name: "Ada Lovelace", email: "ada@test.dev", imageUrl: null },
    signOut: mocks.signOut,
    ...overrides,
  }
}

function renderPanel() {
  render(<ClerkUserPanel />, { wrapper: SidebarProvider })
}

async function openMenu(name: RegExp) {
  await userEvent.click(screen.getByRole("button", { name }))
}

beforeEach(() => {
  vi.clearAllMocks()
  setAuth()
})

describe("ClerkUserPanel", () => {
  it("renders the skeleton until auth has loaded", () => {
    setAuth({ isLoaded: false })
    renderPanel()

    expect(document.querySelector('[data-slot="skeleton"]')).not.toBeNull()
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument()
    expect(screen.queryByText("User")).not.toBeInTheDocument()
  })

  it("falls back to User and No email", async () => {
    setAuth({ user: { name: null, email: null, imageUrl: null } })
    renderPanel()

    // The rail shows the avatar alone, named User; the menu holds the rest.
    await openMenu(/^User$/)
    expect(await screen.findByText("No email")).toBeInTheDocument()
  })

  it("opens Clerk's profile from Account", async () => {
    renderPanel()
    await openMenu(/Ada Lovelace/)

    await userEvent.click(
      await screen.findByRole("menuitem", { name: /Account/ }),
    )
    expect(mocks.clerk.openUserProfile).toHaveBeenCalledOnce()
  })

  it("never offers Organisation", async () => {
    setAuth()
    renderPanel()
    await openMenu(/Ada Lovelace/)

    await screen.findByRole("menuitem", { name: /Log out/ })
    expect(
      screen.queryByRole("menuitem", { name: /Organisation/ }),
    ).not.toBeInTheDocument()
  })

  it("signs out through @app/auth, never Clerk directly", async () => {
    renderPanel()
    await openMenu(/Ada Lovelace/)

    await userEvent.click(
      await screen.findByRole("menuitem", { name: /Log out/ }),
    )
    expect(mocks.signOut).toHaveBeenCalledOnce()
    expect(mocks.clerk.signOut).not.toHaveBeenCalled()
  })
})

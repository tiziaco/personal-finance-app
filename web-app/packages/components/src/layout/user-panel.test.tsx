import type { ComponentProps } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SidebarProvider } from "@app/ui/sidebar"
import { describe, expect, it, vi } from "vitest"

import { UserDetailsPanel, type UserPanelUser } from "./user-panel"

const ada: UserPanelUser = { name: "Ada Lovelace", email: "ada@test.dev" }

// useSidebar() throws outside a SidebarProvider.
function renderPanel(
  props: Partial<ComponentProps<typeof UserDetailsPanel>> = {},
) {
  const onSignOut = vi.fn()
  render(<UserDetailsPanel user={ada} onSignOut={onSignOut} {...props} />, {
    wrapper: SidebarProvider,
  })
  return { onSignOut }
}

async function openMenu() {
  await userEvent.click(screen.getByRole("button", { name: /Ada Lovelace/ }))
}

describe("UserDetailsPanel", () => {
  it("renders a skeleton and no user while there is none", () => {
    renderPanel({ user: null })

    expect(document.querySelector('[data-slot="skeleton"]')).not.toBeNull()
    expect(screen.queryByText("Ada Lovelace")).not.toBeInTheDocument()
  })

  it.each([
    ["Ada", "A"],
    ["Ada Lovelace", "AL"],
    ["Ada King Lovelace", "AL"],
    ["  ada lovelace  ", "AL"],
  ])("shows %j as the initials %s", (name, initials) => {
    renderPanel({ user: { ...ada, name } })

    expect(screen.getByText(initials)).toBeInTheDocument()
  })

  it("offers only Log out without profile handlers", async () => {
    const { onSignOut } = renderPanel()
    await openMenu()

    const logOut = await screen.findByRole("menuitem", { name: /Log out/ })
    expect(
      screen.queryByRole("menuitem", { name: /Account/ }),
    ).not.toBeInTheDocument()

    await userEvent.click(logOut)
    expect(onSignOut).toHaveBeenCalledOnce()
  })

  it("offers Account alone when given only onOpenProfile", async () => {
    const onOpenProfile = vi.fn()
    renderPanel({ onOpenProfile })
    await openMenu()

    const account = await screen.findByRole("menuitem", { name: /Account/ })

    await userEvent.click(account)
    expect(onOpenProfile).toHaveBeenCalledOnce()
  })

  it("shows only the avatar until opened, named for screen readers", () => {
    renderPanel({ user: { name: "Ada", email: "ada@test.dev" } })

    expect(screen.getByRole("button", { name: "Ada" })).toBeInTheDocument()
    expect(screen.queryByText("ada@test.dev")).not.toBeInTheDocument()
  })
})

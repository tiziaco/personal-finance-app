import type { ReactElement } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { SidebarProvider } from "@app/ui/sidebar"
import { describe, expect, it } from "vitest"

import { SettingsDialog, type SettingsTab } from "./settings-dialog"

const TABS: SettingsTab[] = [
  {
    id: "general",
    label: "General",
    icon: <svg />,
    content: <p>General body</p>,
  },
  {
    id: "account",
    label: "Account",
    icon: <svg />,
    content: <p>Account body</p>,
  },
]

// The tab rail is built from sidebar primitives, which throw outside a
// SidebarProvider. The dialog is closed until its trigger is clicked.
async function open(ui: ReactElement) {
  const user = userEvent.setup()
  render(ui, { wrapper: SidebarProvider })
  await user.click(screen.getByRole("button", { name: /settings/i }))
  return user
}

describe("SettingsDialog", () => {
  it("shows the first tab on open", async () => {
    await open(<SettingsDialog tabs={TABS} />)

    expect(await screen.findByText("General body")).toBeInTheDocument()
    expect(screen.queryByText("Account body")).not.toBeInTheDocument()
  })

  it("switches content when another tab is clicked", async () => {
    const user = await open(<SettingsDialog tabs={TABS} />)

    await user.click(await screen.findByRole("button", { name: "Account" }))

    expect(await screen.findByText("Account body")).toBeInTheDocument()
    expect(screen.queryByText("General body")).not.toBeInTheDocument()
  })

  it("renders the footer slot when given one", async () => {
    await open(<SettingsDialog tabs={TABS} footerSlot={<p>Footer here</p>} />)

    expect(await screen.findByText("Footer here")).toBeInTheDocument()
  })

  it("renders no footer without one", async () => {
    await open(<SettingsDialog tabs={TABS} />)
    await screen.findByText("General body")

    expect(document.querySelector('[data-slot="sidebar-footer"]')).toBeNull()
  })
})

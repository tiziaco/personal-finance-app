import type { ComponentProps } from "react"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import {
  ArrowLeftRightIcon,
  ChartColumnIcon,
  HomeIcon,
  MessageSquareIcon,
  SparklesIcon,
} from "lucide-react"
import { SidebarProvider, SidebarTrigger } from "@app/ui/sidebar"
import { describe, expect, it, vi } from "vitest"

import { AppSidebar } from "./app-sidebar"

vi.mock("next/navigation", () => ({ usePathname: () => "/transactions" }))

const ITEMS = [
  { title: "Home", url: "/home", icon: HomeIcon },
  { title: "Transactions", url: "/transactions", icon: ArrowLeftRightIcon },
  { title: "Analytics", url: "/analytics", icon: ChartColumnIcon },
  { title: "Insights", url: "/insights", icon: SparklesIcon },
  { title: "Chat", url: "/chat", icon: MessageSquareIcon },
]

// useSidebar() throws outside a SidebarProvider.
function renderSidebar(props: Partial<ComponentProps<typeof AppSidebar>> = {}) {
  return render(<AppSidebar items={ITEMS} {...props} />, {
    wrapper: SidebarProvider,
  })
}

describe("AppSidebar", () => {
  it("shows every page's label and marks the current one", () => {
    renderSidebar()
    for (const t of ["Home", "Transactions", "Analytics", "Insights", "Chat"])
      expect(screen.getByRole("link", { name: t })).toBeVisible()
    expect(screen.getByRole("link", { name: "Transactions" })).toHaveAttribute(
      "aria-current",
      "page",
    )
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute(
      "aria-current",
    )
  })

  it("puts Settings above the user, last in the rail", () => {
    renderSidebar({
      settingsSlot: <button>Settings</button>,
      userSlot: <button>Ada</button>,
    })
    const settings = screen.getByRole("button", { name: "Settings" })
    const user = screen.getByRole("button", { name: "Ada" })
    expect(
      settings.compareDocumentPosition(user) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it("has the Finsight mark and no collapse trigger", () => {
    renderSidebar()
    expect(screen.getByRole("img", { name: "Finsight" })).toBeInTheDocument()
    expect(document.querySelector('[data-sidebar="trigger"]')).toBeNull()
  })

  it("does not collapse on Ctrl+B", async () => {
    renderSidebar()
    const sidebar = document.querySelector('[data-slot="sidebar"]')
    expect(sidebar).toHaveAttribute("data-state", "expanded")
    await userEvent.keyboard("{Control>}b{/Control}")
    expect(sidebar).toHaveAttribute("data-state", "expanded")
  })

  it("slides out at the rail's width on a phone, not the sheet's default", async () => {
    const width = window.innerWidth
    window.innerWidth = 375
    try {
      render(
        <SidebarProvider>
          <SidebarTrigger />
          <AppSidebar items={ITEMS} />
        </SidebarProvider>,
      )
      await userEvent.click(document.querySelector('[data-sidebar="trigger"]')!)
      const sheet = await screen.findByRole("dialog")
      expect(sheet).toHaveAttribute("data-mobile", "true")
      expect(sheet.className).not.toContain("w-3/4")
      expect(sheet.className).toContain("data-[side=left]:w-(--sidebar-width)")
    } finally {
      window.innerWidth = width
    }
  })
})

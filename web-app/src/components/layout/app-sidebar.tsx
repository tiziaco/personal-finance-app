"use client"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarFooterMenu,
  SidebarGroup,
  SidebarHeader,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { ChevronLeft, ChevronRight, Settings } from "lucide-react"

import { MenuNavigator } from "@/components/layout/nav-sidebar"
import { UserDetailsPanel } from "@/components/layout/user-panel"
import { CompanyLogo } from "@/components/layout/company-logo"
import { SettingsDialog } from "@/components/settings/settings-dialog"

import type { NavItem } from "@/types/nav"

function SidebarEdgeTrigger() {
  const { toggleSidebar, state, isMobile } = useSidebar()

  if (isMobile) return null

  return (
    <button
      onClick={toggleSidebar}
      aria-label="Toggle Sidebar"
      className="absolute top-8 -translate-y-1/2 right-2 translate-x-full z-20 flex items-center justify-center w-4 h-6 bg-sidebar border border-sidebar-border rounded-lg shadow-sm cursor-pointer hover:bg-sidebar-accent text-sidebar-foreground transition-colors"
    >
      {state === "expanded"
        ? <ChevronLeft className="size-3.5" />
        : <ChevronRight className="size-3.5" />
      }
    </button>
  )
}

export function AppSidebar({
  items,
  ...props
}: React.ComponentProps<typeof Sidebar> & {
  items: NavItem[]
}) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarEdgeTrigger />
      <SidebarHeader>
        <CompanyLogo />
      </SidebarHeader>
      <SidebarContent>
        <MenuNavigator items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarGroup>
          <SidebarFooterMenu>
            <SidebarMenuItem>
              <SettingsDialog>
                <SidebarMenuButton size="lg" tooltip="Settings" className="cursor-pointer">
                  <Settings />
                  <span>Settings</span>
                </SidebarMenuButton>
              </SettingsDialog>
            </SidebarMenuItem>
            <UserDetailsPanel />
          </SidebarFooterMenu>
        </SidebarGroup>
      </SidebarFooter>
    </Sidebar>
  )
}

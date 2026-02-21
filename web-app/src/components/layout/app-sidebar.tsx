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
} from "@/components/ui/sidebar"
import { Settings } from "lucide-react"

import { MenuNavigator } from "@/components/layout/nav-sidebar"
import { UserDetailsPanel } from "@/components/layout/user-panel"
import { CompanyLogo } from "@/components/layout/company-logo"
import { SettingsDialog } from "@/components/settings/settings-dialog"

import type { NavItem } from "@/types/nav"

export function AppSidebar({
  items,
  ...props
}: React.ComponentProps<typeof Sidebar> & {
  items: NavItem[]
}) {
  return (
    <Sidebar collapsible="icon" {...props}>
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

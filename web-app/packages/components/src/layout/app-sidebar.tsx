"use client"

import { Fragment } from "react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarFooterMenu,
  SidebarGroup,
  SidebarHeader,
  SidebarMenuItem,
} from "@app/ui/sidebar"
import { MenuNavigator } from "./nav-sidebar"
import { CompanyLogo } from "./company-logo"
import type { NavItem } from "@app/core/types/nav"

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
  items: NavItem[]
  logoSrc: string
  logoAlt?: string
  settingsSlot?: React.ReactNode
  userSlot?: React.ReactNode
}

export function AppSidebar({
  items,
  logoSrc,
  logoAlt,
  settingsSlot,
  userSlot,
  ...props
}: AppSidebarProps) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <CompanyLogo src={logoSrc} alt={logoAlt} />
      </SidebarHeader>
      <SidebarContent>
        <MenuNavigator items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarGroup>
          <SidebarFooterMenu>
            {settingsSlot && <SidebarMenuItem>{settingsSlot}</SidebarMenuItem>}
            {/* Built in a Server Component, the slot reaches React as an
                unkeyed list child and draws a key warning; the Fragment keys it. */}
            <Fragment key="user">{userSlot}</Fragment>
          </SidebarFooterMenu>
        </SidebarGroup>
      </SidebarFooter>
    </Sidebar>
  )
}

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
import { FinsightMark } from "./finsight-mark"
import type { NavItem } from "@app/core/types/nav"

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
  items: NavItem[]
  settingsSlot?: React.ReactNode
  userSlot?: React.ReactNode
}

/**
 * The Finsight rail: the mark on top, the pages, then Settings and the user
 * at the very bottom. It never collapses on a computer; on a phone the
 * primitive shows it as a slide-out.
 */
export function AppSidebar({
  items,
  settingsSlot,
  userSlot,
  ...props
}: AppSidebarProps) {
  return (
    <Sidebar {...props}>
      <SidebarHeader className="items-center pt-5 pb-4">
        <FinsightMark className="w-14" />
      </SidebarHeader>
      <SidebarContent>
        <MenuNavigator items={items} />
      </SidebarContent>
      <SidebarFooter className="pb-4">
        <SidebarGroup>
          <SidebarFooterMenu className="items-center gap-2">
            {settingsSlot && (
              <SidebarMenuItem className="w-full">
                {settingsSlot}
              </SidebarMenuItem>
            )}
            {/* Built in a Server Component, the slot reaches React as an
                unkeyed list child and draws a key warning; the Fragment keys it. */}
            <Fragment key="user">{userSlot}</Fragment>
          </SidebarFooterMenu>
        </SidebarGroup>
      </SidebarFooter>
    </Sidebar>
  )
}

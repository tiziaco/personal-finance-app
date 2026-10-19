"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@app/ui/sidebar"
import type { NavItem } from "@app/core/types/nav"

/** The rail's pages: each a link with its icon above its label. */
export function MenuNavigator({ items }: { items: NavItem[] }) {
  const pathname = usePathname() || "/"

  return (
    <SidebarGroup>
      <SidebarMenu className="gap-2">
        {items.map((item) => {
          const isActive = pathname === item.url
          return (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                size="rail"
                isActive={isActive}
                render={
                  <Link
                    href={item.url}
                    aria-current={isActive ? "page" : undefined}
                  />
                }
              >
                {item.icon && <item.icon />}
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )
        })}
      </SidebarMenu>
    </SidebarGroup>
  )
}

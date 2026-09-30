"use client"

import { HomeIcon, Building2, NotepadText } from "lucide-react"
import type { NavItem } from "@app/core/types/nav"

/**
 * Default hub navigation (used by HubSidebar when no items prop is provided)
 */
export const HUB_NAV: NavItem[] = [
  { title: "Home", url: "/home", icon: HomeIcon },
  { title: "Projects", url: "/projects", icon: Building2 },
  { title: "Orders", url: "/orders", icon: NotepadText },
]

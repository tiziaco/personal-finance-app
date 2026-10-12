"use client"

import { HomeIcon } from "lucide-react"
import type { NavItem } from "@app/core/types/nav"

/**
 * The sidebar's entries. Finance pages add theirs here.
 */
export const HUB_NAV: NavItem[] = [
  { title: "Home", url: "/home", icon: HomeIcon },
]

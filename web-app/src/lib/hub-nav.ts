"use client"

import { HomeIcon, TrendingUp, ArrowLeftRight, Lightbulb } from "lucide-react"
import type { NavItem } from "@/types/nav"

/**
 * Default hub navigation (used by HubSidebar when no items prop is provided)
 */
export const HUB_NAV: NavItem[] = [
  { title: "Home",
    url: "/home",
    icon: HomeIcon
  },
  {
    title: "Transactions",
    url: "/transactions",
    icon: ArrowLeftRight,
  },
  { title: "Stats",
    url: "/stats",
    icon: TrendingUp,
  },
  { title: "Insights",
    url: "/insights",
    icon: Lightbulb,
  },
]

"use client"

import {
  ArrowLeftRightIcon,
  ChartColumnIcon,
  HomeIcon,
  MessageSquareIcon,
  SparklesIcon,
} from "lucide-react"
import type { NavItem } from "@app/core/types/nav"

/**
 * The sidebar's entries. Finance pages add theirs here.
 */
export const HUB_NAV: NavItem[] = [
  { title: "Home", url: "/home", icon: HomeIcon },
  { title: "Transactions", url: "/transactions", icon: ArrowLeftRightIcon },
  { title: "Analytics", url: "/analytics", icon: ChartColumnIcon },
  { title: "Insights", url: "/insights", icon: SparklesIcon },
  { title: "Chat", url: "/chat", icon: MessageSquareIcon },
]

"use client"
import Image from "next/image"
import {
  SidebarMenu,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { useSidebar } from "@/components/ui/sidebar"

export function CompanyLogo() {
  const { state } = useSidebar()

  return (
    <SidebarMenu className="mb-10">
      <SidebarMenuItem>
        <div className="flex items-center gap-2">
          {state === "collapsed" && (
            <Image
              src="/images/logo-small.png"
              alt="App Logo"
              width={40}
              height={40}
              className="h-10 w-10 object-contain"
            />
          )}
          {state !== "collapsed" && (
            <Image
              src="/images/logo-small.png"
              alt="App Logo"
              width={250}
              height={40}
              className="h-10 w-auto object-contain"
            />
          )}
        </div>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
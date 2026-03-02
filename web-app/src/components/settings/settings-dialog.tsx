"use client"

import type React from "react"

import { useState } from "react"
import { Dialog, DialogContent, DialogTrigger, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Settings, Bell, Database, Cog } from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { ServerHealthIndicator } from "@/components/settings/server-status"
import { GeneralSection } from "./sections/general-section"
import { NotificationsSection } from "./sections/notifications-section"
import { DataSection } from "./sections/data-section"

type SettingsSection = "general" | "notifications" | "data"

interface NavItem {
  id: SettingsSection
  label: string
  icon: React.ReactNode
}

const navItems: NavItem[] = [
  { id: "general", label: "General", icon: <Settings className="w-5 h-5" /> },
  { id: "notifications", label: "Notifications", icon: <Bell className="w-5 h-5" /> },
  { id: "data", label: "Data", icon: <Database className="w-5 h-5" /> },
]

export function SettingsDialog({ children }: { children?: React.ReactElement }) {
  const [activeSection, setActiveSection] = useState<SettingsSection>("general")

  const renderSection = () => {
    switch (activeSection) {
      case "general":
        return <GeneralSection />
      case "notifications":
        return <NotificationsSection />
      case "data":
        return <DataSection />
      default:
        return <GeneralSection />
    }
  }

  return (
    <Dialog>
      <DialogTrigger
        render={
          children || (
            <Button variant="ghost" size="default" className="w-full justify-start">
              <Cog />
              <span>Settings</span>
            </Button>
          )
        }
      />
      <DialogContent className="max-w-2xl! h-125 p-0 gap-0 overflow-hidden">
        <div className="flex h-full">
          <Sidebar collapsible="none" className="w-50 border-r flex flex-col">

            <SidebarContent className="p-3 mt-10 flex-1">
              <SidebarMenu>
                {navItems.map((item) => (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      isActive={activeSection === item.id}
                      onClick={() => setActiveSection(item.id)}
                    >
                      {item.icon}
                      {item.label}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarContent>
            
            <SidebarFooter>
              <ServerHealthIndicator />
            </SidebarFooter>
          </Sidebar>
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="overflow-y-auto flex-1">
              <div className="p-6 pt-3">
                <DialogTitle className="text-2xl mb-2 font-semibold capitalize">{activeSection}</DialogTitle>
                <Separator className="mb-6" />
                {renderSection()}
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

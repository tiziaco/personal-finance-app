import { AppSidebar } from "@app/components/layout/app-sidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarMenuButton,
  SidebarTrigger,
} from "@app/ui/sidebar"
import { HUB_NAV } from "@/lib/hub-nav"
import {
  SettingsDialog,
  type SettingsTab,
} from "@app/components/settings/settings-dialog"
import { GeneralSettings } from "@/components/settings/general-settings"
import { DataSettings } from "@/components/settings/data-settings"
import { ServerHealthIndicator } from "@/components/settings/server-status"
import { ClerkUserPanel } from "@/components/layout/clerk-user-panel"
import { QueryProvider } from "@app/api-client/query-provider"
import { UrlStateAdapter } from "@app/data-table/url-state/url-state-adapter"
import { Settings, Database } from "lucide-react"

const SETTINGS_TABS: SettingsTab[] = [
  {
    id: "general",
    label: "General",
    icon: <Settings className="w-5 h-5" />,
    content: <GeneralSettings />,
  },
  {
    id: "data",
    label: "Data",
    icon: <Database className="w-5 h-5" />,
    content: <DataSettings />,
  },
]

export default function HubLayout({ children }: { children: React.ReactNode }) {
  return (
    // The cache lives here, not at the root, so its lifetime is the signed-in
    // shell's: leaving this group unmounts the provider and drops the previous
    // user's data with it. Nothing outside the group reads the API.
    <QueryProvider>
      <UrlStateAdapter>
        <SidebarProvider>
          <AppSidebar
            items={HUB_NAV}
            settingsSlot={
              <SettingsDialog
                tabs={SETTINGS_TABS}
                trigger={
                  <SidebarMenuButton size="rail" className="cursor-pointer">
                    <Settings />
                    <span>Settings</span>
                  </SidebarMenuButton>
                }
                footerSlot={<ServerHealthIndicator />}
              />
            }
            userSlot={<ClerkUserPanel />}
          />
          {/* Phones only: the rail is a slide-out there. */}
          <SidebarTrigger
            size="icon"
            className="text-muted-foreground hover:text-foreground hover:bg-transparent cursor-pointer md:hidden"
          />
          <SidebarInset className="flex flex-col overflow-hidden">
            <div className="flex-1 overflow-auto">
              <div className="min-w-0 px-6 py-6 md:px-8 md:py-7">
                {children}
              </div>
            </div>
          </SidebarInset>
        </SidebarProvider>
      </UrlStateAdapter>
    </QueryProvider>
  )
}

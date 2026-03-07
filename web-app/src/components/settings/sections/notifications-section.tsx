"use client"

import { SettingSection } from "@/components/ui/setting-section"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"

const NOTIFICATION_ITEMS = [
  {
    id: "email",
    label: "Email Alerts",
    description: "Receive weekly spending summaries by email",
  },
  {
    id: "budget",
    label: "Budget Alerts",
    description: "Get notified when you approach a budget limit",
  },
  {
    id: "newsletter",
    label: "Newsletter",
    description: "Tips and updates about new features",
  },
]

export function NotificationsSection() {
  return (
    <div className="space-y-6">
      <SettingSection title="Preferences">
        <div className="space-y-4">
          {NOTIFICATION_ITEMS.map((item) => (
            <div key={item.id} className="flex items-center justify-between gap-4">
              <div>
                <Label>{item.label}</Label>
                <p className="text-xs text-muted-foreground">{item.description}</p>
              </div>
              <Badge variant="secondary">Coming Soon</Badge>
            </div>
          ))}
        </div>
      </SettingSection>
    </div>
  )
}

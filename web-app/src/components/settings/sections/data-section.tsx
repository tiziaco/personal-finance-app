"use client"

import { SettingSection } from "@/components/ui/setting-section"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"

export function DataSection() {
  return (
    <div className="space-y-6">

      <SettingSection title="Data Management">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">Manage or delete your chats</p>
          <Button variant="outline" size="sm" className="border-red-500 text-red-500 hover:text-red-500 hover:bg-red-50">
            Delete All Chats
          </Button>
        </div>
      </SettingSection>

      <SettingSection title="Storage">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Memory Usage</Label>
            <span className="text-sm text-muted-foreground">0 MB</span>
          </div>
          <div className="flex justify-end">
            <Button variant="outline" size="sm">
              Clear Memory
            </Button>
          </div>
        </div>
      </SettingSection>
    </div>
  )
}

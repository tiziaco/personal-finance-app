"use client"

import { SettingSection } from "@/components/ui/setting-section"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"

export function IntegrationsSection() {
  return (
    <div className="space-y-6">
      <SettingSection title="Connected Services">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <Label>Google Drive</Label>
              <p className="text-xs text-muted-foreground">Sync files with Google Drive</p>
            </div>
            <Button variant="outline" size="sm">Connect</Button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <Label>Slack</Label>
              <p className="text-xs text-muted-foreground">Send notifications to Slack</p>
            </div>
            <Button variant="outline" size="sm">Connect</Button>
          </div>
        </div>
      </SettingSection>
    </div>
  )
}

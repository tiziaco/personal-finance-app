"use client"

import { SettingSection } from "@/components/ui/setting-section"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useTheme } from "next-themes"
import { Sun, Moon, Monitor } from "lucide-react"

export function GeneralSection() {
  const { theme, setTheme } = useTheme();

  // Capitalize the theme for display
  const displayTheme = theme ? theme.charAt(0).toUpperCase() + theme.slice(1) : "";

  // Get the icon for the current theme
  const getThemeIcon = () => {
    switch (theme) {
      case "light":
        return <Sun className="w-4 h-4" />
      case "dark":
        return <Moon className="w-4 h-4" />
      case "system":
        return <Monitor className="w-4 h-4" />
      default:
        return null
    }
  };

  return (
    <div className="space-y-6">
      <SettingSection title="Aspect">
        <div className="flex items-center justify-between">
          <Label className="">Theme</Label>
          <Select value={theme} onValueChange={(value) => { if (value) setTheme(value) }}>
            <SelectTrigger className="w-34">
              <SelectValue>
                <div className="flex items-center gap-2">
                  {getThemeIcon()}
                  {displayTheme}
                </div>
              </SelectValue>
            </SelectTrigger>
            <SelectContent className="min-w-34 max-w-34">
              <SelectItem value="light">
                <div className="flex items-center gap-2">
                  <Sun className="w-4 h-4" />
                  Light
                </div>
              </SelectItem>
              <SelectItem value="dark">
                <div className="flex items-center gap-2">
                  <Moon className="w-4 h-4" />
                  Dark
                </div>
              </SelectItem>
              <SelectItem value="system">
                <div className="flex items-center gap-2">
                  <Monitor className="w-4 h-4" />
                  System
                </div>
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </SettingSection>
    </div>
  )
}

"use client"

import { SettingSection } from "@/components/ui/setting-section"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useTheme } from "next-themes"
import { Sun, Moon, Monitor } from "lucide-react"
import { useDateFormat, type DateFormat } from "@/providers/date-format-provider"

const FORMAT_OPTIONS = [
  { value: "de-DE" as DateFormat, label: "DD/MM/YYYY", example: "27.02.2026" },
  { value: "en-US" as DateFormat, label: "MM/DD/YYYY", example: "02/27/2026" },
  { value: "sv-SE" as DateFormat, label: "YYYY-MM-DD", example: "2026-02-27" },
]

export function GeneralSection() {
  const { theme, setTheme } = useTheme();
  const { dateFormat, setDateFormat } = useDateFormat()

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
      <SettingSection title="Regional">
        <div className="flex items-center justify-between">
          <Label>Date Format</Label>
          <Select
            value={dateFormat}
            onValueChange={(value) => { if (value) setDateFormat(value as DateFormat) }}
          >
            <SelectTrigger className="w-34">
              <SelectValue>
                {FORMAT_OPTIONS.find(o => o.value === dateFormat)?.label}
              </SelectValue>
            </SelectTrigger>
            <SelectContent className="min-w-40 max-w-40">
              {FORMAT_OPTIONS.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>
                  <span>{opt.label}</span>
                  <span className="text-muted-foreground text-xs ml-2">{opt.example}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </SettingSection>
    </div>
  )
}

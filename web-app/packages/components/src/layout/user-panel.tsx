"use client"

import { BadgeCheck, LogOut } from "lucide-react"
import { Avatar, AvatarFallback, AvatarImage } from "@app/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@app/ui/dropdown-menu"
import { SidebarMenuItem } from "@app/ui/sidebar"
import { Skeleton } from "@app/ui/skeleton"

export interface UserPanelUser {
  name: string
  email: string
  imageUrl?: string
}

interface UserDetailsPanelProps {
  user: UserPanelUser | null
  onSignOut: () => void
  onOpenProfile?: () => void
}

function getInitials(name: string): string {
  const parts = name.trim().split(" ")
  if (parts.length === 1) return (parts[0]?.[0] ?? "U").toUpperCase()
  return (
    `${parts[0]?.[0] ?? ""}${parts[parts.length - 1]?.[0] ?? ""}`.toUpperCase() ||
    "U"
  )
}

export function UserDetailsPanel({
  user,
  onSignOut,
  onOpenProfile,
}: UserDetailsPanelProps) {
  if (!user) {
    return (
      <SidebarMenuItem className="flex justify-center">
        <Skeleton className="size-9 rounded-lg bg-sidebar-accent" />
      </SidebarMenuItem>
    )
  }

  const initials = getInitials(user.name)

  return (
    <SidebarMenuItem className="flex justify-center">
      <DropdownMenu>
        {/* The rail shows the avatar alone; the name and email head the menu. */}
        <DropdownMenuTrigger
          aria-label={user.name}
          className="cursor-pointer rounded-lg outline-hidden ring-sidebar-ring focus-visible:ring-2"
        >
          <Avatar className="size-9 rounded-lg">
            <AvatarImage src={user.imageUrl} alt={user.name} />
            <AvatarFallback
              className="rounded-lg"
              style={{
                backgroundColor: "var(--primary)",
                color: "var(--primary-foreground)",
              }}
            >
              {initials}
            </AvatarFallback>
          </Avatar>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className="min-w-56 rounded-lg"
          side="right"
          align="end"
          // Clears the rail: half of w-26 minus half the avatar (34px), plus a gap.
          sideOffset={42}
        >
          <DropdownMenuGroup>
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="h-8 w-8 rounded-lg">
                  <AvatarImage src={user.imageUrl} alt={user.name} />
                  <AvatarFallback
                    className="rounded-lg"
                    style={{
                      backgroundColor: "var(--primary)",
                      color: "var(--primary-foreground)",
                    }}
                  >
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">{user.name}</span>
                  <span className="truncate text-xs">{user.email}</span>
                </div>
              </div>
            </DropdownMenuLabel>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          {onOpenProfile && (
            <>
              <DropdownMenuGroup>
                <DropdownMenuItem
                  className="cursor-pointer"
                  onClick={onOpenProfile}
                >
                  <BadgeCheck />
                  Account
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
            </>
          )}
          <DropdownMenuItem className="cursor-pointer" onClick={onSignOut}>
            <LogOut />
            Log out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  )
}

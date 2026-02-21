"use client"

import {
  BadgeCheck,
  ChevronsUpDown,
  LogOut,
} from "lucide-react"
import { useUser } from "@clerk/nextjs"
import { useClerk } from "@clerk/nextjs"

import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { Skeleton } from "../ui/skeleton";


export function UserDetailsPanel() {
  const { isMobile } = useSidebar()
  const { isLoaded, isSignedIn, user } = useUser()
  const { signOut, openUserProfile } = useClerk()

  // Handle sign out
  const handleSignOutClick = async () => {
    await signOut();
  };

  // Show skeleton while Clerk is loading
  if (!isLoaded || !isSignedIn || !user) {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton size="lg">
          <Skeleton className="h-8 w-8 rounded-full bg-sidebar-accent" />
          <div className="grid flex-1 text-left text-sm leading-tight">
            <Skeleton className="h-4 w-24 mb-1 bg-sidebar-accent" />
            <Skeleton className="h-3 w-28 bg-sidebar-accent" />
          </div>
          <ChevronsUpDown className="ml-auto size-4" />
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  }


  // Generate initials from user's name
  const initials = `${user.firstName?.[0] || ''}${user.lastName?.[0] || ''}`.toUpperCase() || 'U';
  const fullName = user.firstName && user.lastName ? `${user.firstName} ${user.lastName}` : user.firstName || user.lastName || 'User';
  const email = user.primaryEmailAddress?.emailAddress || 'No email';

  return (
    <SidebarMenuItem>
      <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                className="cursor-pointer data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
              />
            }
          >
            <Avatar className="h-8 w-8 rounded-lg">
              <AvatarImage src={user.imageUrl} alt={fullName} />
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
              <span className="truncate font-medium">
                {fullName}
              </span>
              <span className="truncate text-xs">
                {email}
              </span>
            </div>
            <ChevronsUpDown className="ml-auto size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "top"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel className="p-0 font-normal">
                <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                  <Avatar className="h-8 w-8 rounded-lg">
                    <AvatarImage src={user.imageUrl} alt={fullName} />
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
                    <span className="truncate font-medium">
                      {fullName}
                    </span>
                    <span className="truncate text-xs">
                      {email}
                    </span>
                  </div>
                </div>
              </DropdownMenuLabel>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem
                className="cursor-pointer"
                onClick={() => openUserProfile()}
              >
                <BadgeCheck />
                Account
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="cursor-pointer"
              onClick={handleSignOutClick}
              >
              <LogOut />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
    </SidebarMenuItem>
  )
}

"use client"

import type { ConversationResponse } from "@app/api-client/types"
import { renameConversationBodyNameMax } from "@app/api-client/zod/conversation"
import { cn } from "@app/core/lib/utils"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@app/ui/alert-dialog"
import { Button } from "@app/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@app/ui/dropdown-menu"
import { Input } from "@app/ui/input"
import { MoreHorizontalIcon, PencilIcon, Trash2Icon } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { CHAT_COPY } from "./copy"
import { IconTooltip } from "./icon-tooltip"

export function ConversationRow({
  conversation,
  active,
  onRename,
  onDelete,
  onNavigate,
}: {
  conversation: ConversationResponse
  active: boolean
  onRename: (name: string) => void
  onDelete: () => void
  onNavigate?: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const label = conversation.name || CHAT_COPY.untitled

  function commit(value: string) {
    setEditing(false)
    const name = value.trim()
    if (name !== "" && name !== conversation.name) onRename(name)
  }

  return (
    <div
      data-slot="conversation-row"
      className={cn(
        "group flex items-center gap-1 rounded-lg pr-1 hover:bg-muted",
        active && "bg-muted",
      )}
    >
      {editing ? (
        <Input
          autoFocus
          aria-label={CHAT_COPY.rename}
          defaultValue={conversation.name}
          maxLength={renameConversationBodyNameMax}
          className="h-8 flex-1"
          onKeyDown={(e) => {
            if (e.key === "Enter") commit(e.currentTarget.value)
            if (e.key === "Escape") setEditing(false)
          }}
          onBlur={(e) => commit(e.currentTarget.value)}
        />
      ) : (
        <Link
          href={`/chat/${conversation.conversation_id}`}
          aria-current={active ? "page" : undefined}
          onClick={onNavigate}
          className="flex-1 truncate px-3 py-2 text-sm"
        >
          {label}
        </Link>
      )}

      <DropdownMenu>
        <IconTooltip label={CHAT_COPY.options}>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Options for ${label}`}
                // Shown by default: a touch screen has no hover to reveal it
                // (Tailwind's hover variants apply only under hover: hover).
                // Only a hover-capable pointer hides it until hover, focus or open.
                className="focus-visible:opacity-100 data-[popup-open]:opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100"
              />
            }
          >
            <MoreHorizontalIcon />
          </DropdownMenuTrigger>
        </IconTooltip>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setEditing(true)}>
            <PencilIcon /> {CHAT_COPY.rename}
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onClick={() => setConfirming(true)}
          >
            <Trash2Icon /> {CHAT_COPY.delete}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{CHAT_COPY.deleteTitle}</AlertDialogTitle>
            <AlertDialogDescription>
              {CHAT_COPY.deleteBody}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{CHAT_COPY.cancel}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                setConfirming(false)
                onDelete()
              }}
            >
              {CHAT_COPY.delete}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

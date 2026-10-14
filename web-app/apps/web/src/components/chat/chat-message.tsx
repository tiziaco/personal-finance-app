"use client"

import {
  ActionBarPrimitive,
  MessagePrimitive,
  useAuiState,
} from "@assistant-ui/react"
import { cn } from "@app/core/lib/utils"
import { Button } from "@app/ui/button"
import { CopyIcon } from "lucide-react"

import { CHAT_COPY } from "./copy"
import { IconTooltip } from "./icon-tooltip"
import { MarkdownText } from "./markdown-text"

export function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end py-2" data-role="user">
      <div className="max-w-[85%] rounded-2xl bg-muted px-4 py-2 text-sm whitespace-pre-wrap break-words">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  )
}

export function AssistantMessage() {
  const status = useAuiState((s) => s.message.status)
  const reason = status?.type === "incomplete" ? status.reason : undefined
  const isLast = useAuiState((s) => s.message.isLast)

  return (
    <MessagePrimitive.Root className="group/message py-2" data-role="assistant">
      <div className="break-words">
        <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
      </div>
      {reason === "cancelled" && (
        <p className="mt-1 text-xs text-muted-foreground">
          {CHAT_COPY.stopped}
        </p>
      )}
      {reason === "error" && (
        <p className="mt-1 text-sm text-destructive">{CHAT_COPY.failed}</p>
      )}
      {/* A fixed-height slot, so the bar never moves the thread: it is
          unmounted only while a reply streams, and an earlier reply's bar is
          revealed by opacity, not mounted on hover (assistant-ui's autohide).
          As with a conversation row's options, only a hover-capable pointer
          hides it; touch and keyboard always reach it. */}
      <div className="mt-1 h-7">
        <ActionBarPrimitive.Root
          hideWhenRunning
          className={cn(
            "flex gap-1",
            !isLast &&
              "focus-within:opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover/message:opacity-100",
          )}
        >
          <IconTooltip label={CHAT_COPY.copy}>
            <ActionBarPrimitive.Copy asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-muted-foreground"
                aria-label={CHAT_COPY.copy}
              >
                <CopyIcon />
              </Button>
            </ActionBarPrimitive.Copy>
          </IconTooltip>
        </ActionBarPrimitive.Root>
      </div>
    </MessagePrimitive.Root>
  )
}

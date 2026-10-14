"use client"

import {
  ActionBarPrimitive,
  MessagePrimitive,
  useAuiState,
} from "@assistant-ui/react"
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

  return (
    <MessagePrimitive.Root className="py-2" data-role="assistant">
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
      <ActionBarPrimitive.Root
        hideWhenRunning
        autohide="not-last"
        className="mt-1 flex gap-1"
      >
        <IconTooltip label={CHAT_COPY.copy}>
          <ActionBarPrimitive.Copy asChild>
            <Button variant="ghost" size="icon-sm" aria-label={CHAT_COPY.copy}>
              <CopyIcon />
            </Button>
          </ActionBarPrimitive.Copy>
        </IconTooltip>
      </ActionBarPrimitive.Root>
    </MessagePrimitive.Root>
  )
}

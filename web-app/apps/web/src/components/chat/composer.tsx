"use client"

import { AuiIf, ComposerPrimitive, useAuiState } from "@assistant-ui/react"
import { sendChatMessageBodyMessageMax } from "@app/api-client/zod/chatbot"
import { Button } from "@app/ui/button"
import { ArrowUpIcon, SquareIcon } from "lucide-react"

import { CHAT_COPY } from "./copy"
import { IconTooltip } from "./icon-tooltip"

// The counter appears once a message gets close to the server's limit.
const COUNTER_FROM = sendChatMessageBodyMessageMax - 500

export function Composer() {
  const length = useAuiState((s) => s.composer.text.length)

  return (
    <ComposerPrimitive.Root className="flex w-full flex-col gap-1 rounded-2xl border bg-background p-2 focus-within:border-ring">
      <ComposerPrimitive.Input
        rows={1}
        autoFocus
        maxLength={sendChatMessageBodyMessageMax}
        placeholder={CHAT_COPY.placeholder}
        aria-label={CHAT_COPY.inputLabel}
        className="max-h-48 min-h-10 w-full resize-none bg-transparent px-2 py-1 text-sm outline-none"
      />
      <div className="flex items-center justify-end gap-2">
        {length >= COUNTER_FROM && (
          <span className="text-xs text-muted-foreground" aria-live="polite">
            {length} / {sendChatMessageBodyMessageMax}
          </span>
        )}
        <AuiIf condition={(s) => !s.thread.isRunning}>
          <IconTooltip label={CHAT_COPY.send}>
            <ComposerPrimitive.Send asChild>
              <Button size="icon" aria-label={CHAT_COPY.send}>
                <ArrowUpIcon />
              </Button>
            </ComposerPrimitive.Send>
          </IconTooltip>
        </AuiIf>
        <AuiIf condition={(s) => s.thread.isRunning}>
          <IconTooltip label={CHAT_COPY.stop}>
            <ComposerPrimitive.Cancel asChild>
              <Button
                size="icon"
                variant="secondary"
                aria-label={CHAT_COPY.stop}
              >
                <SquareIcon />
              </Button>
            </ComposerPrimitive.Cancel>
          </IconTooltip>
        </AuiIf>
      </div>
    </ComposerPrimitive.Root>
  )
}

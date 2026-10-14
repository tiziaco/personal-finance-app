"use client"

import { AuiIf, ThreadPrimitive } from "@assistant-ui/react"
import { Button } from "@app/ui/button"
import { ArrowDownIcon } from "lucide-react"
import type { ReactNode } from "react"

import { AssistantMessage, UserMessage } from "./chat-message"
import { Composer } from "./composer"
import { CHAT_COPY } from "./copy"
import { IconTooltip } from "./icon-tooltip"

function Welcome() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-1 text-center">
      <h2 className="text-lg font-semibold">{CHAT_COPY.welcomeTitle}</h2>
      <p className="text-sm text-muted-foreground">{CHAT_COPY.welcomeBody}</p>
    </div>
  )
}

/** The message list and composer. Render inside an AssistantRuntimeProvider. */
export function Thread({ welcome }: { welcome?: ReactNode }) {
  return (
    <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
      <ThreadPrimitive.Viewport className="relative flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 pt-4">
          <AuiIf condition={(s) => s.thread.isEmpty}>
            {welcome ?? <Welcome />}
          </AuiIf>
          <ThreadPrimitive.Messages
            components={{ UserMessage, AssistantMessage }}
          />
        </div>
        {/* The strip hides the messages scrolling under it, so it takes the
            surface's colour: the page on a phone, ChatShell's card from md. */}
        <div className="sticky bottom-0 mx-auto flex w-full max-w-3xl flex-col items-center gap-2 bg-background px-4 pt-2 pb-4 md:bg-card">
          <IconTooltip label={CHAT_COPY.scrollToBottom}>
            <ThreadPrimitive.ScrollToBottom asChild>
              <Button
                variant="outline"
                size="icon"
                className="rounded-full disabled:invisible"
                aria-label={CHAT_COPY.scrollToBottom}
              >
                <ArrowDownIcon />
              </Button>
            </ThreadPrimitive.ScrollToBottom>
          </IconTooltip>
          <Composer />
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  )
}

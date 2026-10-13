"use client"

import { ApiError } from "@app/api-client"
import { useListChatMessages } from "@app/api-client/endpoints/chatbot"
import { useIsMobile } from "@app/ui/hooks/use-mobile"
import { Button } from "@app/ui/button"
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@app/ui/sheet"
import { Skeleton } from "@app/ui/skeleton"
import { PanelLeftIcon } from "lucide-react"
import { useState, type ReactNode } from "react"

import {
  ChatRuntimeProvider,
  useActiveConversationId,
} from "./chat-runtime-provider"
import { ConversationList } from "./conversation-list"
import { ConversationNotFound } from "./conversation-not-found"
import { CHAT_COPY } from "./copy"
import { Thread } from "./thread"

/**
 * The chat route's two panes. Sized to the viewport inside the dashboard's
 * shared scroller (whose py-4 is the 2rem), so the thread scrolls in its own
 * viewport with the composer pinned beneath it. Nothing outside /chat changes.
 */
export function ChatShell({ children }: { children: ReactNode }) {
  const activeId = useActiveConversationId()
  const isMobile = useIsMobile()
  const [open, setOpen] = useState(false)

  return (
    <ChatRuntimeProvider>
      <div className="flex h-[calc(100svh-2rem)] min-h-0 gap-4">
        {isMobile ? null : (
          <aside className="flex w-64 shrink-0 flex-col border-r pr-2">
            <ConversationList activeId={activeId} />
          </aside>
        )}
        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          {isMobile && (
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={CHAT_COPY.conversations}
                  />
                }
              >
                <PanelLeftIcon />
              </SheetTrigger>
              <SheetContent side="left" className="p-2">
                <SheetTitle className="sr-only">
                  {CHAT_COPY.conversations}
                </SheetTitle>
                <ConversationList
                  activeId={activeId}
                  onNavigate={() => setOpen(false)}
                />
              </SheetContent>
            </Sheet>
          )}
          {children}
        </section>
      </div>
    </ChatRuntimeProvider>
  )
}

/** /chat — a new conversation; nothing is created until the first send. */
export function NewChatPage() {
  return <Thread />
}

/** /chat/[conversationId] — one conversation, or not-found for an unknown or foreign id. */
export function ConversationPage() {
  const activeId = useActiveConversationId()
  const history = useListChatMessages(activeId ?? "", {
    query: { enabled: activeId !== null, meta: { silentError: true } },
  })

  if (history.error instanceof ApiError && history.error.status === 404) {
    return <ConversationNotFound />
  }
  if (history.isPending) return <ChatThreadSkeleton />
  return <Thread />
}

export function ChatThreadSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 pt-4">
      <Skeleton className="ml-auto h-10 w-1/2 rounded-2xl" />
      <Skeleton className="h-24 w-3/4" />
      <Skeleton className="ml-auto h-10 w-1/3 rounded-2xl" />
    </div>
  )
}

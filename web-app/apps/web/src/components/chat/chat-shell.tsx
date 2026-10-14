"use client"

import { ApiError, toastForError } from "@app/api-client"
import { useListChatMessages } from "@app/api-client/endpoints/chatbot"
import { Button } from "@app/ui/button"
import { Card } from "@app/ui/card"
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@app/ui/sheet"
import { Skeleton } from "@app/ui/skeleton"
import { MessagesSquareIcon } from "lucide-react"
import { useEffect, useState, type ReactNode } from "react"

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
 *
 * From md up the panes sit in a Card, rounded and lifted like the floating
 * sidebar. The negative margins pull it out of the scroller's padding to the
 * sidebar's 0.5rem inset, so the two line up. On a phone the Card's surface
 * is switched off: the panes run edge to edge, as the sidebar does there.
 */
export function ChatShell({ children }: { children: ReactNode }) {
  const activeId = useActiveConversationId()
  const [open, setOpen] = useState(false)

  return (
    <ChatRuntimeProvider>
      <Card className="h-[calc(100svh-2rem)] min-h-0 flex-row gap-4 py-0 max-md:overflow-visible max-md:rounded-none max-md:bg-transparent max-md:ring-0 md:-my-2 md:-mr-2 md:h-[calc(100svh-1rem)] md:gap-0 md:rounded-2xl md:shadow-sm">
        {/* The breakpoint is CSS, not useIsMobile(): that flag is false on
            first paint, so a phone would render the desktop aside for a frame
            and the composer would size itself to the squeezed thread. md is
            768px, the hook's MOBILE_BREAKPOINT. */}
        <aside className="hidden w-64 shrink-0 flex-col border-r p-2 md:flex">
          <ConversationList activeId={activeId} />
        </aside>
        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="md:hidden">
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
                <MessagesSquareIcon />
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
          </div>
          {children}
        </section>
      </Card>
    </ChatRuntimeProvider>
  )
}

/** /chat — a new conversation; nothing is created until the first send. */
export function NewChatPage() {
  return <Thread />
}

/** /chat/[conversationId] — one conversation, or not-found for an unknown, foreign or malformed id. */
export function ConversationPage() {
  const activeId = useActiveConversationId()
  const history = useListChatMessages(activeId ?? "", {
    query: { enabled: activeId !== null, meta: { silentError: true } },
  })
  // A malformed id is answered 422 by the path's UUID validation: to the user
  // it is a conversation that doesn't exist, the same as a 404.
  const notFound =
    history.error instanceof ApiError &&
    (history.error.status === 404 || history.error.status === 422)

  // silentError (on this query's every observer) keeps QueryProvider from
  // toasting, and a query's meta can't depend on the status. So the toast it
  // would have shown is raised here, for every error but the not-found below.
  const hasData = history.data !== undefined
  useEffect(() => {
    // Mirrors QueryProvider's rule: a failed refetch behind shown data stays silent.
    if (history.error && !notFound && !hasData) toastForError(history.error)
  }, [history.error, notFound, hasData])

  if (notFound) return <ConversationNotFound />
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

"use client"

import { Button } from "@app/ui/button"
import { Card } from "@app/ui/card"
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@app/ui/sheet"
import { MessagesSquareIcon } from "lucide-react"
import { useState, type ReactNode } from "react"

import {
  ChatRuntimeProvider,
  useActiveConversationId,
} from "./chat-runtime-provider"
import { ConversationList } from "./conversation-list"
import { CHAT_COPY } from "./copy"

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

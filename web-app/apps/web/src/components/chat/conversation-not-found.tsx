import { Button } from "@app/ui/button"
import Link from "next/link"

import { CHAT_COPY } from "./copy"

export function ConversationNotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <p className="text-base font-medium">{CHAT_COPY.notFoundTitle}</p>
      <Button render={<Link href="/chat" />}>{CHAT_COPY.notFoundAction}</Button>
    </div>
  )
}

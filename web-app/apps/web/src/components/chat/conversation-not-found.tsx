import { buttonVariants } from "@app/ui/button"
import Link from "next/link"

import { CHAT_COPY } from "./copy"

export function ConversationNotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <p className="text-base font-medium">{CHAT_COPY.notFoundTitle}</p>
      {/* A link styled as a button, not a Button rendering a Link: Base UI's
          Button expects a native <button>, and nativeButton={false} would give
          the link role="button". */}
      <Link href="/chat" className={buttonVariants()}>
        {CHAT_COPY.notFoundAction}
      </Link>
    </div>
  )
}

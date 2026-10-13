import { toast } from "sonner"
import { ApiError } from "./errors"
import { messages } from "@app/core/constants/messages"

/**
 * Map an error to a toast.
 *
 * SECURITY: status maps to curated copy. Never surface err.message or the
 * response body — server payloads may contain stack traces or internal route
 * names.
 */
export function toastForError(error: unknown): void {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        toast.error(messages.toasts.sessionExpired)
        return
      case 403:
        toast.error(messages.toasts.forbidden)
        return
      case 404:
        toast.error(messages.toasts.notFound)
        return
      case 409:
        toast.error(messages.toasts.conflictError)
        return
      case 422:
        toast.error(messages.toasts.validationError)
        return
      default:
        toast.error(messages.toasts.genericError)
        return
    }
  }
  toast.error(messages.toasts.genericError)
}

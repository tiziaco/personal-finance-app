"use client"

import { useEffect, useRef, useState } from "react"
import { Loader2Icon } from "lucide-react"
import { toast } from "sonner"
import {
  useConfirmTransactionsImport,
  useUploadTransactionsCsv,
} from "@app/api-client/endpoints/transaction-imports"
import type { ImportPreview, ImportResult } from "@app/api-client/types"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@app/ui/dialog"
import { ImportDropZone } from "./import-drop-zone"
import {
  EXPIRED,
  UNAVAILABLE,
  checkFile,
  confirmErrorMessage,
  fileErrorMessage,
  isConfirmInlineError,
  isExpired,
  isUploadInlineError,
} from "./import-errors"
import { initialMapping, type Mapping } from "./import-mapping"
import { ImportMappingReview } from "./import-mapping-review"
import { ImportResultView } from "./import-result"
import { useInvalidateTransactions } from "./use-invalidate-transactions"

type Step =
  | { name: "choose"; error?: string }
  | { name: "review"; preview: ImportPreview; mapping: Mapping; error?: string }
  | { name: "importing"; preview: ImportPreview; mapping: Mapping }
  | { name: "result"; result: ImportResult }

const DESCRIPTIONS: Record<Step["name"], string> = {
  choose: "Upload your bank's CSV export. Nothing is saved until you confirm.",
  review: "Check which column is which, then import.",
  importing: "Every row is categorised as it is imported.",
  result: "Your import is done.",
}

const summary = (r: ImportResult) =>
  `Imported ${r.imported.toLocaleString("en-GB")} · ${r.skipped_duplicates} duplicates skipped · ${r.rejected.length} rejected`

/**
 * Upload → review → import → result. Mounted for as long as the table is, so
 * closing it mid-import loses nothing: the import carries on, the step moves to
 * the result, and a toast offers to reopen it.
 */
export function ImportCsvDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [step, setStep] = useState<Step>({ name: "choose" })
  // Read by hook-level callbacks, which outlive a render and run after unmount.
  const openRef = useRef(open)
  const mountedRef = useRef(false)
  useEffect(() => {
    openRef.current = open
  }, [open])
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])
  const invalidate = useInvalidateTransactions()

  const upload = useUploadTransactionsCsv({
    mutation: { meta: { silentError: isUploadInlineError } },
  })
  const confirm = useConfirmTransactionsImport({
    mutation: {
      // Inline while the dialog is open; once it is closed, QueryProvider's toast tells the user.
      meta: {
        silentError: (error: unknown) =>
          openRef.current && isConfirmInlineError(error),
      },
      onSuccess: async (result) => {
        await invalidate()
        setStep({ name: "result", result })
        if (!openRef.current) {
          toast.success(
            summary(result),
            mountedRef.current
              ? {
                  action: {
                    label: "View details",
                    onClick: () => onOpenChange(true),
                  },
                }
              : undefined,
          )
        }
      },
    },
  })

  const choose = (file: File) => {
    const problem = checkFile(file)
    if (problem) return setStep({ name: "choose", error: problem })
    setStep({ name: "choose" })
    upload.mutate(
      { data: { file } },
      {
        onSuccess: (preview) =>
          setStep({
            name: "review",
            preview,
            mapping: initialMapping(preview),
          }),
        onError: (error) =>
          setStep({ name: "choose", error: fileErrorMessage(error) }),
      },
    )
  }

  const start = (preview: ImportPreview, mapping: Mapping) => {
    setStep({ name: "importing", preview, mapping })
    confirm.mutate(
      { uploadId: preview.upload_id, data: { mapping } },
      {
        onError: (error) =>
          setStep(
            isExpired(error)
              ? { name: "choose", error: EXPIRED }
              : {
                  name: "review",
                  preview,
                  mapping,
                  error: confirmErrorMessage(error),
                },
          ),
      },
    )
  }

  const changeOpen = (next: boolean) => {
    // An import in flight keeps its step; anything else starts over next time.
    if (!next && step.name !== "importing") setStep({ name: "choose" })
    onOpenChange(next)
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import a CSV</DialogTitle>
          <DialogDescription>{DESCRIPTIONS[step.name]}</DialogDescription>
        </DialogHeader>
        {step.name === "choose" && (
          <ImportDropZone
            onFile={choose}
            pending={upload.isPending}
            error={step.error}
          />
        )}
        {step.name === "review" && (
          <ImportMappingReview
            preview={step.preview}
            mapping={step.mapping}
            error={step.error}
            retry={step.error === UNAVAILABLE}
            onChange={(mapping) =>
              setStep({ ...step, mapping, error: undefined })
            }
            onBack={() => setStep({ name: "choose" })}
            onImport={() => start(step.preview, step.mapping)}
          />
        )}
        {step.name === "importing" && (
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <Loader2Icon className="size-6 animate-spin" aria-hidden />
            <p>
              Importing and categorising{" "}
              {step.preview.row_count.toLocaleString("en-GB")} rows…
            </p>
            <p className="text-sm text-muted-foreground">
              You can close this window; the import carries on.
            </p>
          </div>
        )}
        {step.name === "result" && (
          <ImportResultView
            result={step.result}
            onDone={() => changeOpen(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

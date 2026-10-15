"use client"

import { useRef, useState, type DragEvent } from "react"
import { Loader2Icon, UploadIcon } from "lucide-react"
import { Button } from "@app/ui/button"

/** Step 1: drop a file or browse for one. */
export function ImportDropZone({
  onFile,
  pending,
  error,
}: {
  onFile: (file: File) => void
  pending: boolean
  error?: string
}) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  const drop = (event: DragEvent) => {
    event.preventDefault()
    setOver(false)
    const file = event.dataTransfer.files[0]
    if (file && !pending) onFile(file)
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(event) => {
          event.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        className={`flex flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center ${over ? "border-primary bg-muted" : ""}`}
      >
        {pending ? (
          <>
            <Loader2Icon className="size-6 animate-spin" aria-hidden />
            <p>Reading your file…</p>
          </>
        ) : (
          <>
            <UploadIcon className="size-6 text-muted-foreground" aria-hidden />
            <p>Drop a CSV here, or</p>
            <Button
              type="button"
              variant="outline"
              onClick={() => input.current?.click()}
            >
              Browse
            </Button>
          </>
        )}
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          aria-label="CSV file"
          disabled={pending}
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ""
            if (file) onFile(file)
          }}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}

"use client"

import type {
  ImportField,
  ImportPreview,
  MappingSource,
} from "@app/api-client/types"
import { Button } from "@app/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@app/ui/select"
import {
  FIELD_LABELS,
  FIELD_ORDER,
  assignField,
  examples,
  hasRequired,
  type Mapping,
} from "./import-mapping"

const SOURCE_NOTE: Record<MappingSource, string> = {
  remembered: "Using your saved mapping for these columns.",
  proposed: "Suggested by AI. Please check it.",
  none: "Couldn't suggest a mapping: pick the columns yourself.",
}

const FIELD_ITEMS = FIELD_ORDER.map((value) => ({
  value,
  label: FIELD_LABELS[value],
}))

/** Step 2: every column of the file, what it holds, and the field it maps to. */
export function ImportMappingReview({
  preview,
  mapping,
  error,
  retry = false,
  onChange,
  onBack,
  onImport,
}: {
  preview: ImportPreview
  mapping: Mapping
  error?: string
  retry?: boolean
  onChange: (mapping: Mapping) => void
  onBack: () => void
  onImport: () => void
}) {
  const ready = hasRequired(mapping)
  const rows = preview.row_count.toLocaleString("en-GB")
  return (
    <div className="space-y-4">
      <div className="space-y-1 text-sm">
        <p>
          <span className="font-medium">{preview.filename}</span> · {rows} rows
        </p>
        <p className="text-muted-foreground">
          {SOURCE_NOTE[preview.mapping_source]}
        </p>
      </div>
      <ul className="max-h-[50vh] divide-y overflow-y-auto rounded-md border">
        {preview.columns.map((column, index) => {
          const format = column.date_format ?? column.amount_style
          return (
            <li
              key={column.name}
              className="grid gap-2 p-3 sm:grid-cols-[1fr_1fr_11rem] sm:items-center"
            >
              <div className="min-w-0">
                <p className="truncate font-mono text-sm">{column.name}</p>
                {column.empty_rate > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {Math.round(column.empty_rate * 100)}% empty
                  </p>
                )}
              </div>
              <div className="min-w-0 text-sm text-muted-foreground">
                <p className="truncate">
                  {examples(preview, index).join(", ") || "—"}
                </p>
                {format && <p className="text-xs italic">{format}</p>}
              </div>
              <Select
                items={FIELD_ITEMS}
                value={mapping[column.name]}
                onValueChange={(next) =>
                  next &&
                  onChange(
                    assignField(mapping, column.name, next as ImportField),
                  )
                }
              >
                <SelectTrigger
                  aria-label={`${column.name} maps to`}
                  className="w-full"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FIELD_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </li>
          )
        })}
      </ul>
      {!ready && (
        <p className="text-sm text-muted-foreground">
          Map a date, a merchant and an amount.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <Button variant="outline" onClick={onBack}>
          Choose another file
        </Button>
        <Button disabled={!ready} onClick={onImport}>
          {retry ? "Try again" : `Import ${rows} rows`}
        </Button>
      </div>
    </div>
  )
}

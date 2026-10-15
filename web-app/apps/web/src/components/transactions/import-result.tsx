"use client"

import type { ImportResult } from "@app/api-client/types"
import { Button } from "@app/ui/button"

const SHOWN = 100
const count = (n: number) => n.toLocaleString("en-GB")

/** Step 4: what the import did, and the rows it left out. */
export function ImportResultView({
  result,
  onDone,
}: {
  result: ImportResult
  onDone: () => void
}) {
  const counts: [string, number][] = [
    ["Imported", result.imported],
    ["Skipped as duplicates", result.skipped_duplicates],
    ["Filed under Miscellaneous", result.uncategorised],
    ["Rejected", result.rejected.length],
  ]
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {counts.map(([label, n]) => (
          <div key={label} className="rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="text-xl font-semibold tabular-nums">{count(n)}</dd>
          </div>
        ))}
      </dl>
      {result.rejected.length > 0 && (
        <div className="space-y-1">
          <p className="text-sm font-medium">Rejected rows</p>
          <ul className="max-h-48 space-y-0.5 overflow-y-auto text-sm">
            {result.rejected.slice(0, SHOWN).map((r) => (
              <li key={r.row}>
                Row {r.row}: {r.reason}
              </li>
            ))}
          </ul>
          {result.rejected.length > SHOWN && (
            <p className="text-sm text-muted-foreground">
              +{count(result.rejected.length - SHOWN)} more
            </p>
          )}
        </div>
      )}
      <div className="flex justify-end">
        <Button onClick={onDone}>Done</Button>
      </div>
    </div>
  )
}

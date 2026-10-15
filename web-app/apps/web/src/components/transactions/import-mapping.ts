import type { ImportField, ImportPreview } from "@app/api-client/types"

/** Column name to field, for every column of the file. */
export type Mapping = Record<string, ImportField>

export const FIELD_LABELS: Record<ImportField, string> = {
  date: "Date",
  merchant: "Merchant",
  amount: "Amount",
  description: "Description",
  original_category: "Bank's category",
  recurring: "Recurring",
  ignore: "Ignore",
}

export const FIELD_ORDER = Object.keys(FIELD_LABELS) as ImportField[]

const REQUIRED: ImportField[] = ["date", "merchant", "amount"]

export function initialMapping(preview: ImportPreview): Mapping {
  return Object.fromEntries(
    preview.columns.map((c) => [c.name, c.proposed_field]),
  )
}

/** Give `column` the field `field`. A field maps to one column, so the column that held it becomes Ignore. */
export function assignField(
  mapping: Mapping,
  column: string,
  field: ImportField,
): Mapping {
  return Object.fromEntries(
    Object.entries(mapping).map(([name, current]) => {
      if (name === column) return [name, field]
      return [
        name,
        field !== "ignore" && current === field ? "ignore" : current,
      ]
    }),
  )
}

export function hasRequired(mapping: Mapping): boolean {
  const used = new Set(Object.values(mapping))
  return REQUIRED.every((f) => used.has(f))
}

/** Up to two non-empty sample values of the column at `index`. */
export function examples(preview: ImportPreview, index: number): string[] {
  return preview.sample_rows
    .map((row) => row[index])
    .filter((value): value is string => Boolean(value))
    .slice(0, 2)
}

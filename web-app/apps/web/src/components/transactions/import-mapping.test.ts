import { describe, expect, it } from "vitest"
import type { ImportPreview } from "@app/api-client/types"
import {
  assignField,
  examples,
  hasRequired,
  initialMapping,
} from "./import-mapping"

const preview = {
  upload_id: "u",
  filename: "konto.csv",
  row_count: 2,
  mapping_source: "proposed",
  columns: [
    {
      name: "Datum",
      proposed_field: "date",
      empty_rate: 0,
      date_format: "dd.mm.yyyy",
      amount_style: null,
    },
    {
      name: "Empfaenger",
      proposed_field: "merchant",
      empty_rate: 0,
      date_format: null,
      amount_style: null,
    },
    {
      name: "Betrag",
      proposed_field: "amount",
      empty_rate: 0,
      date_format: null,
      amount_style: "1.234,56",
    },
    {
      name: "Notiz",
      proposed_field: "ignore",
      empty_rate: 0.5,
      date_format: null,
      amount_style: null,
    },
  ],
  sample_rows: [
    ["15.01.2026", "REWE", "-3,00", ""],
    ["16.01.2026", "Lidl", "-4,00", "Snacks"],
  ],
} as ImportPreview

describe("import mapping", () => {
  it("starts from the proposal", () => {
    expect(initialMapping(preview)).toEqual({
      Datum: "date",
      Empfaenger: "merchant",
      Betrag: "amount",
      Notiz: "ignore",
    })
  })

  it("moves a taken field, leaving the old column ignored", () => {
    const next = assignField(initialMapping(preview), "Notiz", "merchant")
    expect(next).toEqual({
      Datum: "date",
      Empfaenger: "ignore",
      Betrag: "amount",
      Notiz: "merchant",
    })
  })

  it("lets several columns be ignored", () => {
    const next = assignField(initialMapping(preview), "Datum", "ignore")
    expect(next.Notiz).toBe("ignore")
    expect(next.Datum).toBe("ignore")
  })

  it("needs a date, a merchant and an amount", () => {
    expect(hasRequired(initialMapping(preview))).toBe(true)
    expect(
      hasRequired(assignField(initialMapping(preview), "Betrag", "ignore")),
    ).toBe(false)
  })

  it("takes up to two non-empty examples", () => {
    expect(examples(preview, 3)).toEqual(["Snacks"])
    expect(examples(preview, 1)).toEqual(["REWE", "Lidl"])
  })
})

import { describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ImportPreview } from "@app/api-client/types"
import { ImportMappingReview } from "./import-mapping-review"
import { initialMapping, type Mapping } from "./import-mapping"

const preview = {
  upload_id: "u",
  filename: "konto.csv",
  row_count: 1204,
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
      empty_rate: 0.92,
      date_format: null,
      amount_style: null,
    },
  ],
  sample_rows: [["15.01.2026", "REWE", "-1.234,56", ""]],
} as ImportPreview

function renderReview(mapping: Mapping = initialMapping(preview), extra = {}) {
  const props = { onChange: vi.fn(), onBack: vi.fn(), onImport: vi.fn() }
  render(
    <ImportMappingReview
      preview={preview}
      mapping={mapping}
      {...props}
      {...extra}
    />,
  )
  return props
}

describe("ImportMappingReview", () => {
  it("shows every column with its examples, format and emptiness", () => {
    renderReview()
    expect(screen.getByText("konto.csv")).toBeInTheDocument()
    expect(
      screen.getByText("Suggested by AI. Please check it."),
    ).toBeInTheDocument()
    for (const name of ["Datum", "Empfaenger", "Betrag", "Notiz"])
      expect(screen.getByText(name)).toBeInTheDocument()
    expect(screen.getByText("dd.mm.yyyy")).toBeInTheDocument()
    expect(screen.getByText("1.234,56")).toBeInTheDocument()
    expect(screen.getByText("92% empty")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Import 1,204 rows" }),
    ).toBeEnabled()
  })

  it("moves a taken field when another column picks it", async () => {
    const { onChange } = renderReview()
    await userEvent.click(
      screen.getByRole("combobox", { name: "Notiz maps to" }),
    )
    await userEvent.click(
      within(await screen.findByRole("listbox")).getByRole("option", {
        name: "Merchant",
      }),
    )
    expect(onChange).toHaveBeenCalledWith({
      Datum: "date",
      Empfaenger: "ignore",
      Betrag: "amount",
      Notiz: "merchant",
    })
  })

  it("holds Import until a date, a merchant and an amount are mapped", () => {
    renderReview({ ...initialMapping(preview), Betrag: "ignore" })
    expect(
      screen.getByRole("button", { name: "Import 1,204 rows" }),
    ).toBeDisabled()
    expect(
      screen.getByText("Map a date, a merchant and an amount."),
    ).toBeInTheDocument()
  })

  it("shows an error and offers to try again", () => {
    renderReview(undefined, {
      error: "Categorisation isn't available right now.",
      retry: true,
    })
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Categorisation isn't available right now.",
    )
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled()
  })
})

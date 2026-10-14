import { afterEach, describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { DataTableBulkBar } from "./data-table-bulk-bar"

describe("DataTableBulkBar", () => {
  afterEach(() => vi.restoreAllMocks())

  it("floats fixed over the page, centred on the box it sits in", () => {
    // The table's box: 800px wide, starting 200px in (past a sidebar).
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue(
      DOMRect.fromRect({ x: 200, y: 0, width: 800, height: 400 }),
    )
    render(
      <div>
        <DataTableBulkBar count={2} onClear={() => {}} />
      </div>,
    )
    const bar = screen.getByRole("toolbar", { name: "Bulk actions" })
    const floating = bar.closest<HTMLElement>(".fixed")
    expect(floating).not.toBeNull()
    expect(floating!.style.left).toBe("600px")
  })
})

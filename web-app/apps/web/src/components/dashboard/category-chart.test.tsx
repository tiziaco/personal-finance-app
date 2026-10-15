import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { useListTransactionCategories } from "@app/api-client/endpoints/transactions"
import { CategoryChart } from "./category-chart"

vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useListTransactionCategories: vi.fn(),
}))

describe("CategoryChart", () => {
  it("says so when the month has no spending, instead of an empty donut", () => {
    vi.mocked(useListTransactionCategories).mockReturnValue({
      data: [],
    } as unknown as ReturnType<typeof useListTransactionCategories>)
    render(<CategoryChart slices={[]} />)
    expect(screen.getByText("Spending by category")).toBeInTheDocument()
    expect(screen.getByText("No spending this month.")).toBeInTheDocument()
    expect(screen.queryByRole("list")).not.toBeInTheDocument()
  })
})

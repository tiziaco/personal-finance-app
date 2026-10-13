import { describe, it, expect, vi } from "vitest"
import { renderHook } from "@testing-library/react"
import { useListTransactionCategories } from "@app/api-client/endpoints/transactions"
import { useCategories } from "./use-categories"

vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useListTransactionCategories: vi.fn(),
}))

const mocked = vi.mocked(useListTransactionCategories)
const returns = (data: unknown) =>
  mocked.mockReturnValue({ data } as unknown as ReturnType<
    typeof useListTransactionCategories
  >)

describe("useCategories", () => {
  it("falls back to the slug until the list arrives", () => {
    returns(undefined)
    const { result } = renderHook(() => useCategories())
    expect(result.current.label("food_groceries")).toBe("food_groceries")
    expect(result.current.categories).toEqual([])
  })

  it("labels a known slug and falls back for an unknown one", () => {
    returns([{ value: "food_groceries", label: "Food & Groceries" }])
    const { result } = renderHook(() => useCategories())
    expect(result.current.label("food_groceries")).toBe("Food & Groceries")
    expect(result.current.label("retired")).toBe("retired")
  })
})

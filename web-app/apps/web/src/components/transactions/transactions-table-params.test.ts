import { describe, it, expect } from "vitest"
import { getListTransactionsUrl } from "@app/api-client/endpoints/transactions"
import {
  fromTransactionsFilters,
  hasActiveTransactionsFilters,
  loadTransactionsTableParams,
  toTransactionsFilters,
  toTransactionsQuery,
} from "./transactions-table-params"

const load = (qs: string) =>
  loadTransactionsTableParams(new URLSearchParams(qs))

describe("transactions table params", () => {
  it("round-trips every filter key", () => {
    const values = load(
      "category=salary,atm&amount_min=-100&amount_max=50.5&is_recurring=true&date_mode=range&date_from=2026-01-01&date_to=2026-02-01",
    )
    expect(fromTransactionsFilters(toTransactionsFilters(values))).toEqual({
      category: ["salary", "atm"],
      amount_min: "-100",
      amount_max: "50.5",
      is_recurring: true,
      date_mode: "range",
      date_from: "2026-01-01",
      date_to: "2026-02-01",
    })
  })

  it("trims the search and caps it at 100 characters", () => {
    expect(toTransactionsQuery(load("search=rewe%20")).search).toBe("rewe")
    expect(toTransactionsQuery(load("search=%20%20"))).not.toHaveProperty(
      "search",
    )
    expect(
      toTransactionsQuery(load(`search=${"x".repeat(150)}`)).search,
    ).toHaveLength(100)
  })

  it("drops an unknown category and an unknown ordering", () => {
    const v = load("category=salary,retired_slug&ordering=-fingerprint")
    expect(v.ordering).toBeNull()
    expect(toTransactionsFilters(v).categories).toEqual(["salary"])
  })

  it("builds the query: offset/limit, no date_mode, no unset keys", () => {
    expect(
      toTransactionsQuery(
        load(
          "page=3&search=rewe&date_mode=gte&date_from=2026-01-01&ordering=amount",
        ),
      ),
    ).toEqual({
      offset: 40,
      limit: 20,
      search: "rewe",
      ordering: "amount",
      date_from: "2026-01-01",
    })
  })

  it("never forwards a date the mode hides", () => {
    expect(
      toTransactionsQuery(load("date_mode=gte&date_to=2026-02-01")),
    ).not.toHaveProperty("date_to")
  })

  it("repeats category in the request URL", () => {
    const url = getListTransactionsUrl(
      toTransactionsQuery(load("category=salary,atm")),
    )
    expect(url).toContain("category=salary&category=atm")
  })

  it("knows when the list is narrowed", () => {
    expect(hasActiveTransactionsFilters(load(""))).toBe(false)
    expect(hasActiveTransactionsFilters(load("search=x"))).toBe(true)
    expect(hasActiveTransactionsFilters(load("is_recurring=false"))).toBe(true)
  })
})

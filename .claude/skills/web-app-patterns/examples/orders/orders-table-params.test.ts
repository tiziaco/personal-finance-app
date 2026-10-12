// apps/web/src/components/orders/orders-table-params.test.ts
import { describe, it, expect } from "vitest"
import {
  fromOrdersFilters,
  loadOrdersTableParams,
  toOrdersFilters,
  toOrdersQuery,
} from "./orders-table-params"

const load = (qs: string) => loadOrdersTableParams(new URLSearchParams(qs))

describe("orders table params", () => {
  it("round-trips every filter key", () => {
    const values = load(
      "status=shipped&customer_id=2&created_mode=range&created_from=2026-01-01&created_to=2026-02-01",
    )
    expect(fromOrdersFilters(toOrdersFilters(values))).toEqual({
      status: "shipped",
      customer_id: 2,
      created_mode: "range",
      created_from: "2026-01-01",
      created_to: "2026-02-01",
    })
  })

  it("keeps customer id 0", () => {
    expect(toOrdersFilters(load("customer_id=0")).customer).toBe(0)
  })

  it("drops the hidden date when the mode narrows", () => {
    const filters = toOrdersFilters(
      load("created_mode=range&created_from=2026-01-01&created_to=2026-02-01"),
    )
    const narrowed = fromOrdersFilters({
      ...filters,
      created: { ...filters.created, mode: "gte" },
    })
    expect(narrowed.created_from).toBe("2026-01-01")
    expect(narrowed.created_to).toBeNull()
  })

  it("infers the mode for old links without one", () => {
    expect(toOrdersFilters(load("created_to=2026-02-01")).created.mode).toBe("lte")
  })

  it("builds offset/limit and drops UI-only or unset keys", () => {
    expect(
      toOrdersQuery(load("status=draft&created_mode=gte&created_from=2026-01-01&page=2")),
    ).toEqual({
      offset: 20,
      limit: 20,
      status: "draft",
      created_from: "2026-01-01",
    })
  })

  it("never forwards a date the mode hides, even from a hand-edited link", () => {
    expect(toOrdersQuery(load("created_mode=gte&created_to=2026-02-01"))).not.toHaveProperty(
      "created_to",
    )
  })

  it("drops an ordering field the route does not allow", () => {
    expect(load("ordering=-password").ordering).toBeNull()
  })
})

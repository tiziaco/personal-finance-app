import { describe, it, expect } from "vitest"
import { compactQuery, toListQuery, toOffsetLimit } from "./list-query"

const query = {
  page: 2,
  ordering: "-name",
  search: "",
  filters: { status: "active", owner_id: null },
}

describe("compactQuery", () => {
  it("drops null, undefined and empty strings but keeps 0 and false", () => {
    expect(
      compactQuery({ a: null, b: undefined, c: "", d: 0, e: false, f: "x" }),
    ).toEqual({
      d: 0,
      e: false,
      f: "x",
    })
  })
})

describe("toListQuery", () => {
  it("flattens filters and turns the page into offset/limit, dropping unset keys", () => {
    expect(toListQuery(query, 20)).toEqual({
      offset: 20,
      limit: 20,
      ordering: "-name",
      status: "active",
    })
  })
})

describe("toOffsetLimit", () => {
  it("maps a 1-based page to an offset, clamping below page 1", () => {
    expect(toOffsetLimit(1, 20)).toEqual({ offset: 0, limit: 20 })
    expect(toOffsetLimit(3, 20)).toEqual({ offset: 40, limit: 20 })
    expect(toOffsetLimit(0, 20)).toEqual({ offset: 0, limit: 20 })
  })
})

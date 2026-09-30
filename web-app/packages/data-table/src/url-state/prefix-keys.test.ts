import { describe, it, expect } from "vitest"
import { parseAsInteger, parseAsString } from "nuqs"
import { prefixKeys } from "./prefix-keys"

describe("prefixKeys", () => {
  it("maps every parser key to a prefixed URL key", () => {
    const parsers = {
      page: parseAsInteger.withDefault(1),
      search: parseAsString.withDefault(""),
    }
    expect(prefixKeys(parsers, "orders")).toEqual({
      page: "orders_page",
      search: "orders_search",
    })
  })
})

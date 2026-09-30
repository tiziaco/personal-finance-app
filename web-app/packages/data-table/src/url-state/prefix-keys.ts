/**
 * nuqs `urlKeys` for a list that shares its page with another URL-driven list:
 * { page: "orders_page", search: "orders_search", … }. Pass the same map to
 * the list's loader and createUrlTableStateHook.
 */
export function prefixKeys<T extends object>(
  parsers: T,
  prefix: string,
): { [K in keyof T]: string } {
  return Object.fromEntries(
    Object.keys(parsers).map((key) => [key, `${prefix}_${key}`]),
  ) as {
    [K in keyof T]: string
  }
}

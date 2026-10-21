import type { SignInHeader } from "../api"

/** Rows with a value, as sent; an empty row is a row the user did not fill. */
export function filledHeaders(rows: SignInHeader[]): SignInHeader[] {
  return rows
    .map((row) => ({ name: row.name.trim(), value: row.value }))
    .filter((row) => row.name || row.value)
}

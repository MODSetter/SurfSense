import type { SignInHeader } from "../api"

/** One row to start, as most keyed servers read `Authorization: Bearer <key>`. */
export const STARTING_HEADERS: SignInHeader[] = [
  { name: "Authorization", value: "" },
]

/** A stored plugin's header names, so editing asks only for the values again. */
export function rowsFromNames(names: string[]): SignInHeader[] {
  return names.length
    ? names.map((name) => ({ name, value: "" }))
    : STARTING_HEADERS
}

/** The rows sent: those with a value, named as typed. A name alone is a row left blank. */
export function sentHeaders(rows: SignInHeader[]): SignInHeader[] {
  return rows
    .filter((row) => row.value)
    .map((row) => ({ name: row.name.trim(), value: row.value }))
}

/** Every value has a name to go in. */
export function headersComplete(rows: SignInHeader[]): boolean {
  return rows.every((row) => !row.value || row.name.trim() !== "")
}

import type { ChangeEvent } from "react"

/** The files a file input was given, cleared from it so choosing the same
 *  file again still adds it. */
export function chosenFiles(event: ChangeEvent<HTMLInputElement>): File[] {
  const files = Array.from(event.target.files ?? [])
  event.target.value = ""
  return files
}

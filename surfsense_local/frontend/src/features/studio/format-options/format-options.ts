import type { ReactNode } from "react"

import type { StudioJobCreate } from "../api"

/** What a format adds to the composer and to the job it sends. */
export type FormatOptions = {
  panel: ReactNode
  job: Pick<StudioJobCreate, "format" | "options">
  // False while the format still needs something before it can generate.
  ready: boolean
}

import type { WebGroup } from "./api"

// Where a row stands since the dialog opened.
export type RowState = "adding" | "added" | "already" | "opening" | "opened"

/** What every row and list panel needs from the dialog, passed down as one. */
export type RowActions = {
  states: ReadonlyMap<string, RowState>
  // Lists opened from a row, by that row's link.
  lists: ReadonlyMap<string, WebGroup>
  loadingMore: ReadonlySet<string>
  onAdd: (url: string) => void
  onOpen: (url: string) => void
  onMore: (link: string) => void
}

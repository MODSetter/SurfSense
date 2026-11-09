// Where a row stands since the dialog opened.
export type RowState = "adding" | "added" | "already"

/** What every row needs from the dialog, passed down as one. */
export type RowActions = {
  states: ReadonlyMap<string, RowState>
  onAdd: (url: string) => void
}

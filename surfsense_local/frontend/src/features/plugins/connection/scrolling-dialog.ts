/**
 * A plugin dialog opened over Settings, whose dialog is 48rem tall at most: kept shorter,
 * with its title and buttons fixed and only its fields scrolling, faded at the edges.
 */
export const SCROLLING_DIALOG =
  "flex max-h-[min(40rem,calc(100dvh-4rem))] flex-col"
export const SCROLLING_FORM = "flex min-h-0 flex-1 flex-col"
// The negative margin keeps the scrollbar at the dialog's edge and focus rings unclipped.
// A column, so the viewport fills the space left between title and buttons: a flex item
// has no definite height for the viewport's own `h-full` to resolve against.
export const SCROLLING_FIELDS = "-mx-4 flex flex-1 flex-col"
export const SCROLLING_FIELDS_VIEWPORT = "flex-1 px-4 py-1"

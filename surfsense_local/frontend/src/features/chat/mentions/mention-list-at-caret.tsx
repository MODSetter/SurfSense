import { useLayoutEffect, useRef } from "react"

const GAP_PX = 8
const EDGE_PX = 6

/** Rendered inside the open list: places it above the `@`, inside the composer's
 *  box. Measured once, as it opens, so it stays put while a name is typed. */
export function MentionListAtCaret() {
  const marker = useRef<HTMLSpanElement>(null)
  useLayoutEffect(() => {
    const list = marker.current?.closest<HTMLElement>("[role=listbox]")
    const box = list?.offsetParent
    const selection = window.getSelection()
    if (!list || !box || !selection?.rangeCount) return
    const caret = selection.getRangeAt(0).getBoundingClientRect()
    // A caret in an empty line has no box of its own.
    if (caret.height === 0) return
    const within = box.getBoundingClientRect()
    const furthest = Math.max(
      EDGE_PX,
      within.width - list.offsetWidth - EDGE_PX
    )
    list.style.left = `${Math.min(Math.max(EDGE_PX, caret.left - within.left), furthest)}px`
    list.style.bottom = `${within.bottom - caret.top + GAP_PX}px`
    list.style.marginBottom = "0"
  }, [])
  return <span ref={marker} hidden />
}

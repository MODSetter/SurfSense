import { unstable_useTriggerPopoverScopeContext } from "@assistant-ui/react"
import { useCallback, useEffect, useRef, useState } from "react"

// About four screens of the list, whose rows are not virtualized.
const ROWS_PER_LOAD = 30
const NEAR_END_ROWS = 5
const NEAR_END_PX = 96

/** How many of a list's rows to draw, more as scrolling or the arrow keys near the
 *  end. Everything is in memory, so this bounds rendering rather than fetching. */
export function useRowsLoadedOnScroll(total: number) {
  const { highlightedIndex, highlightIndex } =
    unstable_useTriggerPopoverScopeContext()
  const [loaded, setLoaded] = useState(ROWS_PER_LOAD)
  const loadMore = useCallback(() => setLoaded((n) => n + ROWS_PER_LOAD), [])
  const previous = useRef(highlightedIndex)

  useEffect(() => {
    const before = previous.current
    previous.current = highlightedIndex
    const movingDown = highlightedIndex > before
    if (highlightedIndex >= loaded && highlightedIndex !== before + 1) {
      // The popover wrapped up to the list's true end, which is not drawn.
      highlightIndex(Math.min(loaded, total) - 1)
    } else if (
      movingDown &&
      highlightedIndex >= loaded - NEAR_END_ROWS &&
      loaded < total
    ) {
      loadMore()
    }
  }, [highlightIndex, highlightedIndex, loadMore, loaded, total])

  const rows = useCallback(
    (element: HTMLElement | null) => {
      const list = element?.closest<HTMLElement>("[role=listbox]")
      if (!list) return
      // The popover outlives each list, and a new one starts at its top.
      list.scrollTop = 0
      const onScroll = () => {
        const left = list.scrollHeight - list.scrollTop - list.clientHeight
        if (left < NEAR_END_PX) loadMore()
      }
      list.addEventListener("scroll", onScroll, { passive: true })
      return () => list.removeEventListener("scroll", onScroll)
    },
    [loadMore]
  )

  return { shown: Math.min(loaded, total), rows }
}
